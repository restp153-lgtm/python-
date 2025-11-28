import pandas as pd
from tabulate import tabulate # type: ignore
import sys
import os

# --------------------------
# --- 1. 核心資料載入與預處理 ---
# --------------------------

def load_and_preprocess_data():
    """載入 CSV 檔案並進行必要的資料清理與轉換。"""
    
    # 嘗試不同的編碼，優先使用 utf-8
    encoding_list = ['utf-8', 'cp950'] 
    
    def try_read_csv(filename):
        for encoding in encoding_list:
            try:
                # 相對路徑
                if not os.path.exists(filename):
                    raise FileNotFoundError(f"檔案不存在: {filename}")
                
                # 嘗試讀取
                return pd.read_csv(filename, encoding=encoding)
            except UnicodeDecodeError:
                continue # 嘗試下一個編碼
            except FileNotFoundError:
                raise # 重新拋出 FileNotFoundError
        
        # 如果所有編碼都失敗
        raise UnicodeDecodeError(f"無法使用支援的編碼 ({', '.join(encoding_list)}) 讀取檔案: {filename}")


    try:
        # 載入捷運交通時間 (Mrt Time)
        mrt_time_df = try_read_csv('捷運交通時間.csv')
        
        # 處理 MRT DF：將第一欄設為索引，並移除第一列的 "單位:分" [cite: 1]
        mrt_time_df = mrt_time_df.set_index(mrt_time_df.columns[0])
        mrt_time_df.columns = [col for col in mrt_time_df.columns]
        
        # 將 DataFrame 轉為字典格式以方便查詢: { '起點站': { '目標站': 時間 } }
        mrt_time_db = mrt_time_df.to_dict(orient='index')
        
        # 載入景點資料 (Attraction)
        attraction_df = try_read_csv('景點.csv')
        
        # 預處理景點資料
        # 確保 walk_min 和 rating 是數字
        attraction_df['walk_min'] = pd.to_numeric(attraction_df['walk_min'], errors='coerce')
        attraction_df['rating'] = pd.to_numeric(attraction_df['rating'], errors='coerce')

        #  tags 分號分隔的字串轉為列表
        attraction_df['tags'] = attraction_df['tags'].astype(str).apply(lambda x: x.split(';') if ';' in x else [x])
        
        # 移除無效的景點資料
        attraction_df.dropna(subset=['walk_min', 'rating'], inplace=True)
        
        # 獲取所有目標捷運站名稱 (用於 Min-Max 比較)
        mrt_stations = list(mrt_time_df.index)
        
        return mrt_time_db, attraction_df, mrt_stations

    except FileNotFoundError as e:
        print(f"錯誤：找不到檔案 {e.filename}。請確認檔案在相同目錄中。")
        sys.exit(1)
    except Exception as e:
        print(f"資料載入或處理時發生錯誤: {e}")
        sys.exit(1)

# ----------------------------------------
# --- 2. Step 1: 最公平會合捷運站 (Min-Max) ---
# ----------------------------------------

def find_fair_mrt_station(user_starts, mrt_time_db, all_stations):
    """
    實作 Min-Max 公平演算法，找出最公平的會合捷運站。
    """
    
    max_time_table = {}
    
    # 遍歷所有可能的目標會合站 [cite: 1]
    for target_station in all_stations:
        max_travel_time = 0
        
        # 遍歷所有使用者，找出到該目標站所需的最久時間
        for start_station in user_starts:
            time = mrt_time_db.get(start_station, {}).get(target_station)
            
            if time is None:
                max_travel_time = float('inf') 
                break 
            
            if time > max_travel_time:
                max_travel_time = time
        
        max_time_table[target_station] = max_travel_time

    # 找出 min_max_time (Min of Max)
    if not max_time_table or all(v == float('inf') for v in max_time_table.values()):
        return [], 0
        
    min_max_time = min(max_time_table.values())

    # 找出所有達到這個最小值的站
    fair_stations = [
        station for station, max_time in max_time_table.items() 
        if max_time == min_max_time
    ]
    
    return fair_stations, min_max_time

# ----------------------------------------
# --- 3. Step 2: 景點加權分數計算與排序 ---
# ----------------------------------------

def calculate_attraction_score(candidate_df, user_tags, num_users):
    """
    計算景點的加權分數並排序。
    """
    
    # 權重設定
    WEIGHT_TAGS = 0.4
    WEIGHT_WALK = 0.3
    WEIGHT_PRICE = 0.2
    WEIGHT_RATING = 0.1
    
    # --- 1. tags標籤分數 (權重 * 0.4) ---
    # 分數 = (景點標籤與使用者標籤匹配次數) / N
    
    def get_tag_match_score(attraction_tags):
        # attraction_tags 是列表 (例如: ['逛街', '散步'])
        match_count = 0
        for tag in attraction_tags:
            # 計算這個景點的 tag 在所有使用者偏好中出現的總次數
            match_count += user_tags.count(tag) 
        
        return match_count / num_users
    
    candidate_df['score_tag'] = candidate_df['tags'].apply(get_tag_match_score)
    
    # --- 2. walk_min 走路時長分數 (權重 * 0.3) ---
    # 分數 = (13 - walk_min) / 11 
    MIN_WALK = 2
    MAX_WALK = 13
    WALK_RANGE = MAX_WALK - MIN_WALK
    
    # 計算分數
    candidate_df['score_walk'] = (MAX_WALK - candidate_df['walk_min']) / WALK_RANGE
    # 處理 walk_min 超出範圍的情況
    candidate_df.loc[candidate_df['walk_min'] <= MIN_WALK, 'score_walk'] = 1.0
    candidate_df.loc[candidate_df['walk_min'] >= MAX_WALK, 'score_walk'] = 0.0
    
    # --- 3. price_level 價格分數 (權重 * 0.2) ---
    # low=1, medium=0.5, high=0 
    price_map = {'low': 1.0, 'medium': 0.5, 'high': 0.0}
    
    def get_price_score(price_level_str):
        # 處理 price_level 包含多個值 (如 low;medium;high) 的情況 
        levels = str(price_level_str).lower().split(';')
        # 越便宜分數越高，如果有低價選項，取最高分
        return max(price_map.get(level, 0.0) for level in levels) if levels else 0.0
        
    candidate_df['score_price'] = candidate_df['price_level'].apply(get_price_score)
    
    # --- 4. rating 評價分數 (權重 * 0.1) ---
    # 分數 = rating / 5 
    candidate_df['score_rating'] = candidate_df['rating'] / 5.0
    
    # --- 5. 計算總分 (加權和) ---
    candidate_df['total_score'] = (
        candidate_df['score_tag'] * WEIGHT_TAGS +
        candidate_df['score_walk'] * WEIGHT_WALK +
        candidate_df['score_price'] * WEIGHT_PRICE +
        candidate_df['score_rating'] * WEIGHT_RATING
    )
    
    # 排序：依總分由高到低
    final_recommendations_df = candidate_df.sort_values(
        by='total_score', ascending=False
    ).reset_index(drop=True)
    
    final_recommendations_df['rank'] = final_recommendations_df.index + 1
    
    # 轉為列表輸出
    return final_recommendations_df.to_dict('records')


# --------------------------
# --- 4. 輸出與流程控制 ---
# --------------------------

def display_results(results, start_index=0, count=3):
    """顯示排名結果的表格"""
    
    if not results:
        print("抱歉，沒有找到符合條件的景點。")
        return 0 
        
    display_data = results[start_index : start_index + count]
    
    if not display_data:
        return 0
        
    # 準備表格數據
    table_headers = [
        "名次", "捷運站", "景點名稱", "總分", 
        "Tag分數(0.4)", "Walk分數(0.3)", "Price分數(0.2)", "Rating分數(0.1)"
    ]
    
    table_rows = []
    for item in display_data:
        table_rows.append([
            item['rank'],
            item['mrt_station'],
            item['name'],
            f"{item['total_score']:.4f}",
            f"{item['score_tag']:.4f}",
            f"{item['score_walk']:.4f}",
            f"{item['score_price']:.4f}",
            f"{item['score_rating']:.4f}",
        ])
    
    # 使用 tabulate 庫美化輸出
    print(tabulate(table_rows, headers=table_headers, tablefmt="fancy_grid"))
    
    return len(display_data)

def main():
    """主程式"""
    
    # 載入資料
    mrt_time_db, attraction_df, mrt_stations = load_and_preprocess_data()
    
    # 輸出問候語
    print("✨ 大家好! 我是約會地點推薦器! ✨")
    
    # 1. 獲取使用者數量 N
    while True:
        try:
            n_input = input("請輸入出發的總人數 (2~10): ")
            N = int(n_input)
            if 2 <= N <= 10:
                break
            else:
                print("人數必須在 2 到 10 之間，請重新輸入。")
        except ValueError:
            print("請輸入有效的數字。")

    # 2. 獲取每個使用者的出發站和偏好標籤
    user_starts = []
    user_tags = [] 
    
    # 定義可接受的標籤列表 (根據題目說明)
    VALID_TAGS = {'景點', '散步', '看展', '咖啡廳', '逛街', '電影', '手作', '夜市'}
    
    for i in range(1, N + 1):
        while True:
            try:
                print(f"\n--- 第 {i} 位使用者 ---")
                
                # 提示使用者輸入
                print(f"可選捷運站: {', '.join(mrt_stations)}")
                print(f"可選標籤: {', '.join(VALID_TAGS)}")
                
                user_input = input("請輸入出發捷運站 和 景點偏好 (以空白隔開，例如: 台北車站 逛街): ").split()
                
                if len(user_input) != 2:
                    print("輸入格式錯誤，請輸入 '捷運站 標籤'。")
                    continue
                    
                start_station, preference_tag = user_input[0], user_input[1]
                
                # 驗證輸入
                if start_station not in mrt_stations:
                    print(f"無效的捷運站名: {start_station}。請確認輸入的是指定10站之一。")
                    continue
                
                if preference_tag not in VALID_TAGS:
                    print(f"無效的偏好標籤: {preference_tag}。請確認輸入的是指定8種標籤之一。")
                    continue

                user_starts.append(start_station)
                user_tags.append(preference_tag)
                break
                
            except Exception as e:
                print(f"輸入發生錯誤: {e}")
                
    print("\n--- ⏳ 約會地點推薦系統計算中... ⏳ ---\n")

    # --- Step 1: 找出最公平會合站 ---
    fair_stations, min_max_time = find_fair_mrt_station(user_starts, mrt_time_db, mrt_stations)
    
    if not fair_stations:
        print("無法計算出公平會面地點。請檢查捷運站資料或輸入。")
        return

    # --- Step 2: 篩選景點並計算分數 ---
    
    # 篩選候選景點：屬於公平會合站的景點
    candidate_attractions_df = attraction_df[
        attraction_df['mrt_station'].isin(fair_stations)
    ].copy() 
    
    if candidate_attractions_df.empty:
        print(f"最公平會面地點為 {', '.join(fair_stations)}，但附近沒有推薦景點。")
        return

    # 計算並排序分數
    final_recommendations = calculate_attraction_score(candidate_attractions_df, user_tags, N)

    # --- 輸出結果 ---
    
    # 輸出 Step 1 結果
    print(f"🎉 各位的最公平會面地點是: **{', '.join(fair_stations)}**")
    print(f"🕰️ 最長通勤時間為: **{min_max_time} 分鐘**")
    print("\n--- 🔝 以下是推薦大家去的景點 (前 3 名)！ 🔝 ---")
    
    # 輸出前三名
    current_display_index = 0
    
    displayed_count = display_results(final_recommendations, current_display_index, 3)
    current_display_index += displayed_count
    
    # 流程控制
    while True:
        if current_display_index >= len(final_recommendations):
            print("\n已顯示所有推薦景點。")
            break
            
        control = input("\n輸入 **1** 繼續顯示後續名次，輸入 **q** 結束程式: ").lower()
        
        if control == 'q':
            break
        elif control == '1':
            print("\n--- 繼續顯示 ---")
            displayed_count = display_results(final_recommendations, current_display_index, 3)
            current_display_index += displayed_count
            if displayed_count == 0:
                break
        else:
            print("無效輸入，請輸入 1 或 q。")

    # 輸出結語
    print("\n--- 💖 以上是推薦的目的地 祝各位約會開心! 💖 ---")

if __name__ == '__main__':
    main()