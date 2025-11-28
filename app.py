import streamlit as st
import pandas as pd
import os

# --------------------------
# --- 1. 資料載入與預處理 (適應 Streamlit) ---
# --------------------------

# 將 Tabulate 函式包裝起來，以便在 Streamlit 中顯示
def format_results_for_streamlit(results):
    if not results:
        return pd.DataFrame()
        
    table_headers = [
        "名次", "捷運站", "景點名稱", "總分", 
        "Tag分數(0.4)", "Walk分數(0.3)", "Price分數(0.2)", "Rating分數(0.1)"
    ]
    
    table_rows = []
    for item in results:
        table_rows.append({
            "名次": item['rank'],
            "捷運站": item['mrt_station'],
            "景點名稱": item['name'],
            "總分": f"{item['total_score']:.4f}",
            "Tag分數(0.4)": f"{item['score_tag']:.4f}",
            "Walk分數(0.3)": f"{item['score_walk']:.4f}",
            "Price分數(0.2)": f"{item['score_price']:.4f}",
            "Rating分數(0.1)": f"{item['score_rating']:.4f}",
        })
    
    return pd.DataFrame(table_rows, columns=table_headers)


@st.cache_data
def load_and_preprocess_data():
    """載入 CSV 檔案並進行必要的資料清理與轉換。"""
    
    encoding_list = ['utf-8', 'cp950'] 
    
    def try_read_csv(filename):
        for encoding in encoding_list:
            try:
                if not os.path.exists(filename):
                    raise FileNotFoundError(f"檔案不存在: {filename}")
                return pd.read_csv(filename, encoding=encoding)
            except UnicodeDecodeError:
                continue 
            except FileNotFoundError:
                raise 
        raise UnicodeDecodeError(f"無法使用支援的編碼 ({', '.join(encoding_list)}) 讀取檔案: {filename}")

    # --- 載入區塊 ---
    try:
        # 1. 載入捷運交通時間 (Mrt Time)
        mrt_time_df = try_read_csv('捷運交通時間.csv')
        mrt_time_df = mrt_time_df.set_index(mrt_time_df.columns[0])
        mrt_time_db = mrt_time_df.to_dict(orient='index')
        mrt_stations = list(mrt_time_df.index)
        
        # 2. 載入景點資料 (Attraction)
        attraction_df = try_read_csv('景點.csv')
        
        # --- 預處理區塊 ---
        attraction_df['walk_min'] = pd.to_numeric(attraction_df['walk_min'], errors='coerce')
        attraction_df['rating'] = pd.to_numeric(attraction_df['rating'], errors='coerce')
        
        # 處理 tags (使用分號 ';' 分隔)
        attraction_df['tags'] = attraction_df['tags'].astype(str).apply(lambda x: x.split(';') if ';' in x else [x])
        
        attraction_df.dropna(subset=['walk_min', 'rating'], inplace=True)
        
        return mrt_time_db, attraction_df, mrt_stations

    except Exception as e:
        st.error(f"資料載入或處理失敗: {e}. 請檢查您的 CSV 檔案名稱和編碼。")
        return None, None, None

# ----------------------------------------
# --- 2. Step 1: 最公平會合捷運站 (Min-Max) ---
# ----------------------------------------

def find_fair_mrt_station(user_starts, mrt_time_db, all_stations):
    """
    實作 Min-Max 公平演算法，找出最公平的會合捷運站。
    """
    max_time_table = {}
    
    for target_station in all_stations:
        max_travel_time = 0
        for start_station in user_starts:
            time = mrt_time_db.get(start_station, {}).get(target_station)
            
            if time is None:
                max_travel_time = float('inf') 
                break 
            
            if time > max_travel_time:
                max_travel_time = time
        
        max_time_table[target_station] = max_travel_time

    if not max_time_table or all(v == float('inf') for v in max_time_table.values()):
        return [], 0
        
    min_max_time = min(max_time_table.values())

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
    def get_tag_match_score(attraction_tags):
        match_count = 0
        for tag in attraction_tags:
            match_count += user_tags.count(tag) 
        return match_count / num_users
    
    candidate_df['score_tag'] = candidate_df['tags'].apply(get_tag_match_score)
    
    # --- 2. walk_min 走路時長分數 (權重 * 0.3) ---
    MIN_WALK = 2
    MAX_WALK = 13
    WALK_RANGE = MAX_WALK - MIN_WALK
    
    candidate_df['score_walk'] = (MAX_WALK - candidate_df['walk_min']) / WALK_RANGE
    candidate_df.loc[candidate_df['walk_min'] <= MIN_WALK, 'score_walk'] = 1.0
    candidate_df.loc[candidate_df['walk_min'] >= MAX_WALK, 'score_walk'] = 0.0
    
    # --- 3. price_level 價格分數 (權重 * 0.2) ---
    price_map = {'low': 1.0, 'medium': 0.5, 'high': 0.0}
    
    def get_price_score(price_level_str):
        levels = str(price_level_str).lower().split(';')
        return max(price_map.get(level, 0.0) for level in levels) if levels else 0.0
        
    candidate_df['score_price'] = candidate_df['price_level'].apply(get_price_score)
    
    # --- 4. rating 評價分數 (權重 * 0.1) ---
    candidate_df['score_rating'] = candidate_df['rating'] / 5.0
    
    # --- 5. 計算總分 (加權和) ---
    candidate_df['total_score'] = (
        candidate_df['score_tag'] * WEIGHT_TAGS +
        candidate_df['score_walk'] * WEIGHT_WALK +
        candidate_df['score_price'] * WEIGHT_PRICE +
        candidate_df['score_rating'] * WEIGHT_RATING
    )
    
    # 排序
    final_recommendations_df = candidate_df.sort_values(
        by='total_score', ascending=False
    ).reset_index(drop=True)
    
    final_recommendations_df['rank'] = final_recommendations_df.index + 1
    
    return final_recommendations_df.to_dict('records')


# --------------------------
# --- 4. Streamlit 介面 ---
# --------------------------

def app():
    st.set_page_config(page_title="約會地點推薦系統", layout="wide")
    st.title("💖 約會地點推薦系統 (Min-Max 公平演算法)")
    st.markdown("---")

    # 載入資料 (使用 Streamlit cache 避免重複讀取)
    mrt_time_db, attraction_df, mrt_stations = load_and_preprocess_data()
    
    if mrt_time_db is None:
        st.stop() # 如果資料載入失敗，則停止執行
    
    VALID_TAGS = ['景點', '散步', '看展', '咖啡廳', '逛街', '電影', '手作', '夜市']
    
    # --- 側邊欄輸入區 ---
    with st.sidebar:
        st.header("👥 使用者輸入")
        
        # 1. 總人數 N
        N = st.slider("請輸入總人數 N (2~10)", min_value=2, max_value=10, value=3)
        
        user_inputs = []
        for i in range(1, N + 1):
            st.subheader(f"使用者 {i}")
            
            # 2. 出發捷運站 (使用 selectbox 方便選擇)
            start_station = st.selectbox(
                f"請選擇使用者 {i} 的出發捷運站:", 
                options=mrt_stations, 
                key=f"start_{i}"
            )
            
            # 3. 偏好標籤
            preference_tag = st.selectbox(
                f"請選擇使用者 {i} 的偏好標籤:", 
                options=VALID_TAGS, 
                key=f"tag_{i}"
            )
            
            user_inputs.append({
                "start": start_station,
                "tag": preference_tag
            })

    # --- 主區域結果展示 ---
    if st.button("🚀 啟動推薦!"):
        if not user_inputs:
            st.warning("請在側邊欄輸入使用者資訊。")
            return

        # 準備 Step 1 輸入資料
        user_starts = [u['start'] for u in user_inputs]
        user_tags = [u['tag'] for u in user_inputs]
        
        # --- Step 1: 找出最公平會合站 ---
        st.header("1️⃣ Step 1: 最公平會合捷運站 (Min-Max)")
        
        fair_stations, min_max_time = find_fair_mrt_station(user_starts, mrt_time_db, mrt_stations)
        
        if not fair_stations:
            st.error("無法計算出公平會面地點。請檢查捷運站資料。")
            return

        st.success(f"🎉 **最公平會面地點**: **{', '.join(fair_stations)}**")
        st.info(f"🕰️ **最長通勤時間**: **{min_max_time} 分鐘**")

        # --- Step 2: 篩選景點並計算分數 ---
        st.header("2️⃣ Step 2: 景點加權分數計算與排序")
        
        candidate_attractions_df = attraction_df[
            attraction_df['mrt_station'].isin(fair_stations)
        ].copy() 
        
        if candidate_attractions_df.empty:
            st.warning(f"最公平會面地點附近沒有推薦景點。")
            return

        final_recommendations = calculate_attraction_score(candidate_attractions_df, user_tags, N)

        # 格式化並顯示結果
        results_df = format_results_for_streamlit(final_recommendations)
        
        st.subheader("🔝 推薦景點排名 (加權總分計算)")
        st.dataframe(results_df, use_container_width=True)
        
        st.markdown("---")
        st.balloons() # 加爽的
        st.success("💖 以上是推薦的目的地 祝各位約會開心! 💖")

if __name__ == '__main__':
    app()