import streamlit as st
import pandas as pd
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import io
import traceback

# ページ設定
st.set_page_config(page_title="オッズ一括取得ツール", page_icon="🏇", layout="centered")
st.title("🏇 netkeiba オッズ一括取得")
st.write("上位人気一覧のURLを貼り付けて「取得開始」を押してください。")

# URL入力欄
start_url = st.text_input("netkeiba URL", placeholder="https://race.netkeiba.com/odds/index.html?type=b0...")

def setup_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    # クラウド環境とローカル環境の両方に対応するための設定
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except:
        # Streamlit Cloudなどの環境用フォールバック
        driver = webdriver.Chrome(options=options)
    return driver

# タブクリック等の関数（以前と同じロジックなので一部省略せず記載）
def click_tab(driver, target_word1, target_word2=None):
    links = driver.find_elements(By.TAG_NAME, "a")
    for link in links:
        text = link.text
        if target_word2:
            if target_word1 in text and target_word2 in text:
                driver.execute_script("arguments[0].click();", link)
                time.sleep(3)
                return True
        else:
            if target_word1 in text and "人気" not in text:
                driver.execute_script("arguments[0].click();", link)
                time.sleep(3)
                return True
    return False

def extract_tansho_fukusho(driver):
    horse_data = {}
    soup = BeautifulSoup(driver.page_source, "html.parser")
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cols = row.find_all(["td", "th"])
            if len(cols) >= 5:
                col_texts = [col.get_text(separator=" ", strip=True).replace(" - ", "-") for col in cols]
                num_text = col_texts[1]
                if num_text.isdigit():
                    num = int(num_text)
                    if num not in horse_data:
                        horse_data[num] = {"馬番": num, "馬名": col_texts[4], "単勝": "", "複勝": ""}
                    if "-" in col_texts[-1]:
                        horse_data[num]["複勝"] = col_texts[-1]
                    else:
                        horse_data[num]["単勝"] = col_texts[-1]
    return list(horse_data.values())

def extract_matrix_odds(driver, data_name):
    matrix_data = []
    select_elems = driver.find_elements(By.TAG_NAME, "select")
    
    if select_elems: # 3連系
        select = Select(select_elems[0])
        wait = WebDriverWait(driver, 10)
        for index in range(len(select.options)):
            try:
                select_elem = wait.until(EC.presence_of_element_located((By.TAG_NAME, "select")))
                select = Select(select_elem)
                opt_text = select.options[index].text.strip()
                if not opt_text: continue
                base_num1 = ''.join(filter(str.isdigit, opt_text.split()[0]))
                
                select.select_by_index(index)
                time.sleep(1.5)
                
                soup = BeautifulSoup(driver.page_source, "html.parser")
                for table in soup.find_all("table"):
                    headers = [th.get_text(strip=True) for th in table.find_all("th") if th.get_text(strip=True).isdigit()]
                    if not headers: continue
                    for row in table.find_all("tr"):
                        tds = row.find_all("td")
                        for i in range(0, len(tds), 2):
                            if i + 1 >= len(tds): break
                            num3 = tds[i].get_text(strip=True)
                            odds_text = tds[i+1].get_text(separator=" ", strip=True).replace(",", "")
                            if num3.isdigit() and any(char.isdigit() for char in odds_text):
                                col_idx = i // 2
                                if col_idx < len(headers):
                                    num2 = headers[col_idx]
                                    if data_name == "3連単":
                                        comb_str = f"{base_num1}-{num2}-{num3}"
                                    else:
                                        nums = sorted([int(base_num1), int(num2), int(num3)])
                                        comb_str = f"{nums[0]}-{nums[1]}-{nums[2]}"
                                    if not any(d.get("組み合わせ") == comb_str for d in matrix_data):
                                        matrix_data.append({"組み合わせ": comb_str, "オッズ": odds_text})
            except:
                continue
    else: # 馬連・枠連など
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in table.find_all("th") if th.get_text(strip=True).isdigit()]
            if not headers: continue
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                for i in range(0, len(tds), 2):
                    if i + 1 >= len(tds): break
                    num1 = tds[i].get_text(strip=True)
                    odds_text = tds[i+1].get_text(separator=" ", strip=True).replace(" - ", "-").replace(",", "")
                    if num1.isdigit() and any(char.isdigit() for char in odds_text):
                        col_idx = i // 2
                        if col_idx < len(headers):
                            num2 = headers[col_idx]
                            if data_name == "馬単":
                                comb_str = f"{num1}-{num2}"
                            else:
                                comb_str = f"{min(int(num1), int(num2))}-{max(int(num1), int(num2))}"
                            if not any(d.get("組み合わせ") == comb_str for d in matrix_data):
                                matrix_data.append({"組み合わせ": comb_str, "オッズ": odds_text})
    return matrix_data


# 実行ボタンが押された時の処理
if st.button("取得開始", type="primary", use_container_width=True):
    if not start_url:
        st.error("URLを入力してください。")
    else:
        # 進捗表示用の枠
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # スマホ版URLをPC版URLに自動変換
            fixed_url = start_url.replace("race.sp.netkeiba.com", "race.netkeiba.com").replace("sp.netkeiba.com", "netkeiba.com")
            
            # ★確認用：変換されたURLを画面に青い枠で表示する
            st.info(f"✅ 以下のPC用URLに変換してアクセスします:\n{fixed_url}")
            
            status_text.text("ブラウザを起動中...")
            driver = setup_browser()
            driver.get(fixed_url)
            time.sleep(3)
            
            # 結果を格納する辞書
            all_dfs = {}
            
            # 1. 単勝・複勝
            status_text.text("単勝・複勝を取得中... (1/7)")
            click_tab(driver, "単勝", "複勝")
            tan_fuku = extract_tansho_fukusho(driver)
            if tan_fuku:
                all_dfs["単勝・複勝"] = pd.DataFrame(tan_fuku).sort_values("馬番")
            progress_bar.progress(15)

            # 2. 枠連
            status_text.text("枠連を取得中... (2/7)")
            if click_tab(driver, "枠連"):
                waku = extract_matrix_odds(driver, "枠連")
                if waku:
                    df = pd.DataFrame(waku)
                    df['sort_key'] = df['組み合わせ'].apply(lambda x: [int(n) for n in x.split('-')])
                    all_dfs["枠連"] = df.sort_values('sort_key').drop('sort_key', axis=1)
            progress_bar.progress(30)

            # 3. 馬連
            status_text.text("馬連を取得中... (3/7)")
            if click_tab(driver, "馬連"):
                umaren = extract_matrix_odds(driver, "馬連")
                if umaren:
                    df = pd.DataFrame(umaren)
                    df['sort_key'] = df['組み合わせ'].apply(lambda x: [int(n) for n in x.split('-')])
                    all_dfs["馬連"] = df.sort_values('sort_key').drop('sort_key', axis=1)
            progress_bar.progress(45)

            # 4. ワイド
            status_text.text("ワイドを取得中... (4/7)")
            if click_tab(driver, "ワイド"):
                wide = extract_matrix_odds(driver, "ワイド")
                if wide:
                    df = pd.DataFrame(wide)
                    df['sort_key'] = df['組み合わせ'].apply(lambda x: [int(n) for n in x.split('-')])
                    all_dfs["ワイド"] = df.sort_values('sort_key').drop('sort_key', axis=1)
            progress_bar.progress(60)

            # 5. 馬単
            status_text.text("馬単を取得中... (5/7)")
            if click_tab(driver, "馬単"):
                umatan = extract_matrix_odds(driver, "馬単")
                if umatan:
                    df = pd.DataFrame(umatan)
                    df['s1'] = df['組み合わせ'].apply(lambda x: int(x.split('-')[0]))
                    df['s2'] = df['組み合わせ'].apply(lambda x: int(x.split('-')[1]))
                    all_dfs["馬単"] = df.sort_values(['s1', 's2']).drop(['s1', 's2'], axis=1)
            progress_bar.progress(75)

            # 6. 3連複
            status_text.text("3連複を取得中... (6/7)")
            if click_tab(driver, "3連複"):
                sanrenpuku = extract_matrix_odds(driver, "3連複")
                if sanrenpuku:
                    df = pd.DataFrame(sanrenpuku)
                    df['sort_key'] = df['組み合わせ'].apply(lambda x: [int(n) for n in x.split('-')])
                    all_dfs["3連複"] = df.sort_values('sort_key').drop('sort_key', axis=1)
            progress_bar.progress(85)

            # 7. 3連単
            status_text.text("3連単を取得中... (7/7) ※少し時間がかかります")
            if click_tab(driver, "3連単"):
                sanrentan = extract_matrix_odds(driver, "3連単")
                if sanrentan:
                    df = pd.DataFrame(sanrentan)
                    df['s1'] = df['組み合わせ'].apply(lambda x: int(x.split('-')[0]))
                    df['s2'] = df['組み合わせ'].apply(lambda x: int(x.split('-')[1]))
                    df['s3'] = df['組み合わせ'].apply(lambda x: int(x.split('-')[2]))
                    all_dfs["3連単"] = df.sort_values(['s1', 's2', 's3']).drop(['s1', 's2', 's3'], axis=1)
            progress_bar.progress(100)
            status_text.text("取得完了！Excelファイルを生成しています...")

            driver.quit()

            # Excelファイル（バイナリ）の作成
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                for sheet_name, df in all_dfs.items():
                    df.to_excel(writer, index=False, sheet_name=sheet_name)
            
            excel_data = output.getvalue()

            st.success("🎉 すべてのオッズ取得が完了しました！")
            
            # ダウンロードボタン
            st.download_button(
                label="📥 Excelファイル（全券種）をダウンロード",
                data=excel_data,
                file_name="netkeiba_all_odds.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            driver.quit()
