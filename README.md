💖 約會地點推薦系統 (Min-Max 公平演算法)
🌟 專案簡介 (Project Introduction)
本專案是一個多人約會地點推薦系統，旨在解決「多個朋友從不同地點出發，如何找到一個最公平、最滿意的會面地點？」的問題。
我們使用 Min-Max 公平演算法 (Min–Max Fairness) 來確定「最公平會合捷運站」，確保所有參與者中通勤時間最久的人，其花費的時間最短。隨後，系統會根據所有人的共同偏好和景點特性，計算加權分數並推薦最佳景點。
✨ 核心演算法與流程 (Core Algorithm & Flow)
系統運作分為兩大步驟：
Step 1: 最公平會合捷運站 (Min–Max Fairness)
輸入：$N$ 個使用者的出發捷運站。
目標：在 10 個目標捷運站中，找到一個會合站 $T$。
計算：對於每個潛在的會合站 $T$，計算所有使用者到站所需時間的最大值 ($\text{Max Time} = \max(\text{Time}_{\text{user}_i \to T})$)。
輸出：找出所有 $\text{Max Time}$ 中的最小值 ($\text{Min Max Time}$)，該站即為最公平的會合站。
Step 2: 景點加權分數計算 (Weighted Scoring)
系統篩選 Step 1 確定的會合站附近的景點，並根據四項標準計算總分並排名。
評分項目權重說明0~1 分數計算公式偏好標籤 (Tags)0.4反映景點與所有使用者偏好的平均匹配度。$\text{Score}_{\text{Tag}} = \frac{\text{匹配的使用者標籤次數}}{\text{總人數 } N}$走路時長 (Walk_min)0.3越短越好 (範圍 2~13 分鐘)。$\text{Score}_{\text{Walk}} = \frac{13 - \text{walk\_min}}{13 - 2}$價格等級 (Price_level)0.2越便宜越好 ($\text{low}=1, \text{medium}=0.5, \text{high}=0$)。
查表法，取景點所含價格級別中的最高分數。評價 (Rating)0.1越高越好 (範圍 0~5)。$\text{Score}_{\text{Rating}} = \frac{\text{Rating}}{5}$總分 (Total Score) 公式：$$\text{Total Score} = 0.4 \times \text{Score}_{\text{Tag}} + 0.3 \times \text{Score}_{\text{Walk}} + 0.2 \times \text{Score}_{\text{Price}} + 0.1 \times \text{Score}_{\text{Rating}}$$🚀 如何啟動應用程式 (Getting Started)本應用程式是基於 Streamlit 框架開發的，可以透過網頁瀏覽器進行互動。1. 部署連結 (Deployed Link)若應用程式已部署在 Streamlit Community Cloud，請在此處填入您的公開網址。
[👉 點擊此處前往應用程式網址 [Your Streamlit URL Here]]2. 本地運行 (Local Setup)如果您想在本地電腦運行本專案：A. 環境要求Python 3.8+B. 安裝依賴請在您的終端機中運行以下指令安裝所需的函式庫：Bashpip install -r requirements.txt
# 或者手動安裝：pip install streamlit pandas tabulate
C. 運行應用程式確保您的專案目錄包含 app.py、捷運交通時間.csv、景點.csv 和 requirements.txt 檔案。Bashstreamlit run app.py
應用程式將會在您的瀏覽器中自動開啟 (http://localhost:8501)。
📁 專案檔案結構 (File Structure)/mrt-dating-recommender/
├── app.py                 # Streamlit 網頁應用程式主程式
├── 捷運交通時間.csv       # 資料庫 1: 捷運站間的交通時間數據
├── 景點.csv               # 資料庫 2: 景點資訊、標籤、價格和評價數據
├── requirements.txt       # Python 依賴清單 (用於部署)
└── README.md              # 專案說明文件 (您正在閱讀的這個檔案)
🛠️ 開發技術棧 (Tech Stack)程式語言：Python網頁框架：Streamlit數據處理：Pandas介面美化：Tabulate (用於終端機輸出輔助)