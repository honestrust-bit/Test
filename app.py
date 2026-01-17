import streamlit as st
import random
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from kiwipiepy import Kiwi
import extra_streamlit_components as stx
import datetime
import re

# ==========================================
# [Backend] 구글 시트 매니저 (변경 없음)
# ==========================================
# (이전과 동일한 백엔드 로직입니다. 안정성을 위해 그대로 유지합니다.)
class GoogleSheetManager:
    def __init__(self):
        try:
            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            if "gcp_service_account" in st.secrets:
                creds_dict = dict(st.secrets["gcp_service_account"])
            else:
                st.error("Secrets 설정이 필요합니다."); st.stop()
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open("memory_game_db")
            
            try: self.users_ws = self.sheet.worksheet("users")
            except: self.users_ws = self.sheet.add_worksheet("users", 100, 10)
            if not self.users_ws.row_values(1): self.users_ws.append_row(["user_id", "password", "level", "xp", "title"])
            
            try: self.collections_ws = self.sheet.worksheet("collections")
            except: self.collections_ws = self.sheet.add_worksheet("collections", 100, 10)
            
            headers = ["user_id", "card_text", "grade", "collected_at", "quest_name", "count"]
            if not self.collections_ws.row_values(1): self.collections_ws.append_row(headers)

            try: self.quests_ws = self.sheet.worksheet("quests")
            except: self.quests_ws = self.sheet.add_worksheet("quests", 100, 5)
            if not self.quests_ws.row_values(1): self.quests_ws.append_row(["quest_name", "content", "created_by", "created_at"])

        except Exception as e:
            st.error(f"구글 시트 연결 오류: {e}"); st.stop()

    def login(self, user_id, password):
        records = self.users_ws.get_all_records()
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and (password == "" or str(row['password']) == str(password)):
                return row, i + 2
        return None, None

    def register(self, user_id, password):
        records = self.users_ws.get_all_records()
        for row in records:
            if str(row['user_id']) == str(user_id): return False
        self.users_ws.append_row([user_id, password, 1, 0, "견습 가디언"])
        return True

    def save_quest(self, name, content, creator):
        records = self.quests_ws.get_all_records()
        for row in records:
            if row['quest_name'] == name: return False
        self.quests_ws.append_row([name, content[:45000], creator, str(datetime.date.today())])
        return True

    def get_quest_list(self):
        return self.quests_ws.get_all_records()

    def process_reward(self, user_id, card_text, current_level, current_xp, row_idx, quest_name):
        try: records = self.collections_ws.get_all_records()
        except: records = []
        
        found_idx = -1; current_count = 0; current_grade = "NORMAL"
        for i, row in enumerate(records):
            if str(row['user_id']) == str(user_id) and row['card_text'] == card_text and row.get('quest_name') == quest_name:
                found_idx = i + 2; current_count = row.get('count', 1); current_grade = row.get('grade', 'NORMAL'); break
        
        status = ""; final_grade = current_grade
        if found_idx != -1:
            new_count = current_count + 1
            if new_count >= 7: new_grade = "LEGEND"
            elif new_count >= 3: new_grade = "RARE"
            else: new_grade = current_grade
            self.collections_ws.update_cell(found_idx, 6, new_count)
            self.collections_ws.update_cell(found_idx, 3, new_grade)
            self.collections_ws.update_cell(found_idx, 4, str(datetime.date.today()))
            status = "UPGRADE"; final_grade = new_grade; xp_gain = 10 + (new_count * 2)
        else:
            rand = random.random()
            if rand < 0.05: final_grade = "LEGEND"
            elif rand < 0.20: final_grade = "RARE"
            else: final_grade = "NORMAL"
            self.collections_ws.append_row([user_id, card_text, final_grade, str(datetime.date.today()), quest_name, 1])
            status = "NEW"; xp_gain = 50 if final_grade == "LEGEND" else 30 if final_grade == "RARE" else 20

        new_xp = current_xp + xp_gain
        new_level, req_xp = current_level, current_level * 100
        if new_xp >= req_xp: new_level += 1; new_xp -= req_xp
        
        self.users_ws.update_cell(row_idx, 3, new_level)
        self.users_ws.update_cell(row_idx, 4, new_xp)
        return final_grade, xp_gain, new_level, new_xp, status, current_count + 1 if found_idx != -1 else 1

    def get_collections(self, user_id):
        try: return [c for c in self.collections_ws.get_all_records() if str(c['user_id']) == str(user_id)]
        except: return []

# ==========================================
# [Design] 닥터 스트레인지 도서관 테마 🧙‍♂️
# ==========================================
def apply_game_style():
    st.markdown("""
        <style>
        /* 고풍스럽고 마법적인 폰트 임포트 */
        @import url('https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@700&family=Spectral:wght@400;600&display=swap');
        
        /* 전체 폰트 설정: 기본은 Spectral(명조 계열), 제목은 Cinzel(장식용) */
        html, body, [class*="css"] {
            font-family: 'Spectral', serif;
            color: #e8dcb5 !important; /* 양피지색 텍스트 */
        }
        
        h1, h2, h3 {
            font-family: 'Cinzel Decorative', cursive !important;
            color: #d4af37 !important; /* 황금색 제목 */
            text-shadow: 0 0 10px rgba(212, 175, 55, 0.5);
        }

        /* 배경: 신비로운 어둠의 마법 도서관 */
        .stApp {
            background: linear-gradient(135deg, #0d0d1a 0%, #1a0f2e 50%, #2c1e12 100%);
            background-attachment: fixed;
        }

        /* 메인 컨테이너 UI (카드/창) - 고대 마법서 느낌 */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: rgba(30, 20, 10, 0.85) !important; /* 어두운 가죽/나무 질감 */
            border: 2px solid #d4af37 !important; /* 황금색 테두리 */
            border-radius: 8px !important;
            padding: 25px !important;
            box-shadow: 0 0 20px rgba(212, 175, 55, 0.2), inset 0 0 30px rgba(0,0,0,0.5) !important;
            background-image: url('https://www.transparenttextures.com/patterns/aged-paper.png'); /* 종이 질감 오버레이 */
        }
        
        /* 컨테이너 내부 텍스트 색상 강제 지정 */
        div[data-testid="stVerticalBlockBorderWrapper"] p,
        div[data-testid="stVerticalBlockBorderWrapper"] span,
        div[data-testid="stVerticalBlockBorderWrapper"] div {
            color: #e8dcb5 !important; /* 양피지색 */
        }

        /* 버튼: 마법 룬 문자판 느낌 */
        .stButton > button {
            background: linear-gradient(to bottom, #5e4b3c, #3d2b1f);
            color: #d4af37 !important; /* 황금색 글씨 */
            border: 2px solid #d4af37;
            border-radius: 5px;
            height: 55px;
            font-family: 'Cinzel Decorative', cursive;
            font-size: 1.2rem;
            text-shadow: 0 0 5px rgba(212, 175, 55, 0.7);
            box-shadow: 0 4px 0 #2a1a10;
            transition: all 0.2s;
        }
        .stButton > button:hover {
            background: linear-gradient(to bottom, #7e5b4c, #4d3b2f);
            box-shadow: 0 0 15px rgba(212, 175, 55, 0.8); /* 빛나는 효과 */
        }
        .stButton > button:active {
            transform: translateY(4px);
            box-shadow: 0 0 0 #2a1a10;
        }
        
        /* 입력창: 오래된 종이에 쓰는 느낌 */
        .stTextInput input {
            background-color: rgba(255, 255, 255, 0.1) !important;
            color: #e8dcb5 !important;
            border: 1px solid #d4af37 !important;
            border-radius: 4px;
            font-family: 'Spectral', serif;
        }
        .stTextInput label { color: #d4af37 !important; font-family: 'Cinzel Decorative', cursive !important;}

        /* 경험치 바: 마력이 차오르는 느낌 (파란색/보라색) */
        .stProgress > div > div > div > div {
            background: linear-gradient(to right, #4b0082, #0000ff, #00ffff);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        }

        /* 아바타 둥둥 효과 (느리고 신비롭게) */
        @keyframes mysteriousFloat { 
            0%, 100% { transform: translateY(0); filter: drop-shadow(0 0 10px rgba(212, 175, 55, 0.3)); } 
            50% { transform: translateY(-15px); filter: drop-shadow(0 0 20px rgba(0, 255, 255, 0.5)); } 
        }
        .avatar-emoji { 
            font-size: 110px; 
            animation: mysteriousFloat 4s ease-in-out infinite; 
        }
        .user-info-box { 
            background: rgba(0,0,0,0.6); 
            padding: 8px 20px; 
            border: 2px solid #d4af37; 
            border-radius: 4px;
            color: #d4af37;
            font-family: 'Cinzel Decorative', cursive;
        }
        
        /* 탭 스타일 */
        .stTabs [data-baseweb="tab"] {
            color: #e8dcb5;
        }
        .stTabs [aria-selected="true"] {
            color: #d4af37 !important;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# [Logic] 앱 실행
# ==========================================
st.set_page_config(page_title="Sanctum of Knowledge", page_icon="🧙‍♂️", layout="centered")
apply_game_style()

@st.cache_resource
def load_resources(): return Kiwi(), GoogleSheetManager()
kiwi, gm = load_resources()
cookie_manager = stx.CookieManager()

if 'user_id' not in st.session_state: st.session_state.user_id = None; st.session_state.difficulty = "쉬움 (빈칸 1개)"

time.sleep(0.1)
cookie_id = cookie_manager.get("my_game_id")
if st.session_state.user_id is None and cookie_id:
    try:
        records = gm.users_ws.get_all_records()
        for i, row in enumerate(records):
            if str(row['user_id']) == str(cookie_id):
                st.session_state.user_id = row['user_id']; st.session_state.user_row_idx = i + 2
                st.session_state.level = row['level']; st.session_state.xp = row['xp']
                st.toast(f"마법사 {cookie_id}님, 귀환을 환영합니다.", icon="🧙‍♂️"); break
    except: pass

# 화면 1: 로그인
if st.session_state.user_id is None:
    st.title("🧙‍♂️ Sanctum of Knowledge")
    st.markdown("<div style='text-align:center; color:#d4af37; font-style:italic;'>고대 지식의 수호자가 되기 위한 여정</div>", unsafe_allow_html=True)
    st.write("")
    tab1, tab2 = st.tabs(["서고 입장", "수호자 등록"])
    with tab1:
        lid = st.text_input("마법사명 (ID)")
        lpw = st.text_input("봉인 주문 (PW)", type="password")
        remember_me = st.checkbox("마력 유지 (자동 로그인)")
        if st.button("입장하기", type="primary"):
            user_data, row_idx = gm.login(lid, lpw)
            if user_data:
                st.session_state.user_id = lid; st.session_state.user_row_idx = row_idx
                st.session_state.level = user_data['level']; st.session_state.xp = user_data['xp']
                if remember_me: cookie_manager.set("my_game_id", lid, expires_at=datetime.datetime.now() + datetime.timedelta(days=7))
                st.rerun()
            else: st.error("존재하지 않는 마법사이거나 주문이 틀렸습니다.")
    with tab2:
        rid = st.text_input("새로운 마법사명")
        rpw = st.text_input("새로운 봉인 주문", type="password")
        if st.button("등록하기"):
            if gm.register(rid, rpw): st.success("등록되었습니다. 입장을 진행해주세요."); time.sleep(1); st.rerun()
            else: st.error("이미 존재하는 마법사명입니다.")

# 화면 2: 로비
elif 'page' not in st.session_state or st.session_state.page == 'main':
    u_id, lv, xp = st.session_state.user_id, st.session_state.level, st.session_state.xp
    req_xp = lv * 100
    
    # 아바타 진화 (마법 아이템/존재)
    if lv < 5: avatar = "📜"      # 고대 주문서
    elif lv < 10: avatar = "🧿"    # 아가모토의 눈(느낌)
    elif lv < 20: avatar = "🔮"    # 예언의 수정구
    else: avatar = "🧙‍♂️"           # 소서러 슈프림
    
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        diff = st.select_slider("🔥 마법 수행 난이도", options=["쉬움 (빈칸 1개)", "보통 (30%)", "어려움 (50%)", "지옥 (전부)"])
        st.session_state.difficulty = diff
    with col_top2:
        if st.button("로그아웃"):
            cookie_manager.delete("my_game_id"); st.session_state.user_id = None; st.rerun()
            
    st.markdown(f"""
        <div class="main-avatar-container">
            <div class="avatar-emoji">{avatar}</div>
            <div class="user-info-box">Lv.{lv} {u_id}</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.write(f"**마력(EXP)** ({xp} / {req_xp})")
    st.progress(min(xp / req_xp, 1.0))

    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚔️ 금지된 서고 탐색"): st.session_state.page = 'dungeon'; st.rerun()
    with col2:
        if st.button("📖 아카식 레코드"): st.session_state.page = 'collection'; st.rerun()

# 화면 3: 퀘스트 (인터리브 방식 유지)
elif st.session_state.page == 'dungeon':
    if st.button("🏠 중앙 홀로 귀환"): 
        st.session_state.page = 'main'
        if 'curr_ans' in st.session_state: del st.session_state.curr_ans
        st.rerun()
        
    st.header("📜 금지된 지식의 서")
    tab_list, tab_upload = st.tabs(["주문서 선택", "새 주문서 기록"])
    
    with tab_list:
        quests = gm.get_quest_list()
        if not quests: st.info("해독할 주문서가 없습니다.")
        else:
            q_names = [q['quest_name'] for q in quests]
            if 'selected_quest_name' not in st.session_state: st.session_state.selected_quest_name = "선택 안함"
            selected_q = st.selectbox("해독할 주문서:", ["선택 안함"] + q_names)
            st.session_state.selected_quest_name = selected_q

            if selected_q != "선택 안함":
                q_content = next(item['content'] for item in quests if item['quest_name'] == selected_q)
                if st.button(f"✨ '{selected_q}' 해독 시작"):
                    st.session_state.sents = [s.text for s in kiwi.split_into_sents(q_content) if len(s.text)>5]
                    st.session_state.q_idx = 0
                    if 'curr_ans' in st.session_state: del st.session_state.curr_ans
                    st.rerun()

    with tab_upload:
        new_q_name = st.text_input("주문서 이름")
        uploaded = st.file_uploader("기록 업로드 (.txt)", type=['txt'])
        if st.button("기록하기"):
            if new_q_name and uploaded:
                txt_content = uploaded.getvalue().decode('utf-8')
                if gm.save_quest(new_q_name, txt_content, st.session_state.user_id):
                    st.success("주문서가 서고에 기록되었습니다."); time.sleep(1); st.rerun()
                else: st.error("이미 존재하는 이름입니다.")

    st.divider()

    if 'sents' in st.session_state and st.session_state.sents:
        if 'curr_ans' not in st.session_state:
            curr_sent = st.session_state.sents[st.session_state.q_idx % len(st.session_state.sents)]
            tokens = kiwi.tokenize(curr_sent)
            STOPWORDS = {'다음','사항','경우','포함','관련','해당','각','호','목','조','항','위','아래','전','후','및','등','이','그','저','것','수','때','중','가지','누구','무엇','따름','의','를','가'}
            nouns = [t.form for t in tokens if t.tag in ['NNG', 'NNP'] and len(t.form)>1 and t.form not in STOPWORDS]
            
            if not nouns: st.session_state.q_idx += 1; st.rerun()
            
            diff = st.session_state.difficulty
            unique_nouns = list(set(nouns))
            target_nouns = []
            if "쉬움" in diff: target_nouns = [random.choice(unique_nouns)]
            elif "보통" in diff: k = max(1, int(len(unique_nouns) * 0.3)); target_nouns = random.sample(unique_nouns, k)
            elif "어려움" in diff: k = max(1, int(len(unique_nouns) * 0.5)); target_nouns = random.sample(unique_nouns, k)
            else: target_nouns = unique_nouns

            matches = []
            for t in target_nouns:
                for m in re.finditer(re.escape(t), curr_sent): matches.append((m.start(), m.group()))
            matches.sort(key=lambda x: x[0])
            
            st.session_state.curr_sent = curr_sent; st.session_state.curr_matches = matches
            st.session_state.curr_targets = [m[1] for m in matches]; st.session_state.curr_ans = "ACTIVE"

        # [고대 마법서 디자인 컨테이너]
        with st.container(border=True): 
            with st.form("btl", clear_on_submit=False):
                user_inputs = []; last_idx = 0; full_text = st.session_state.curr_sent
                
                for i, (start, word) in enumerate(st.session_state.curr_matches):
                    pre_text = full_text[last_idx:start]
                    if pre_text: st.write(pre_text)
                    
                    col_blank, col_rest = st.columns([1, 0.1])
                    with col_blank:
                        val = st.text_input(f"룬 문자 ({i+1}) 입력", key=f"ans_{st.session_state.q_idx}_{i}")
                    user_inputs.append(val)
                    last_idx = start + len(word)
                
                if last_idx < len(full_text): st.write(full_text[last_idx:])
                
                st.write("")
                if st.form_submit_button("✨ 주문 시전"):
                    all_correct = True; wrong_indices = []
                    for i, target in enumerate(st.session_state.curr_targets):
                        if user_inputs[i].strip() != target: all_correct = False; wrong_indices.append(i+1)
                    
                    if all_correct:
                        g, gain, nl, nx, stat, cnt = gm.process_reward(
                            st.session_state.user_id, st.session_state.curr_sent, 
                            st.session_state.level, st.session_state.xp, st.session_state.user_row_idx,
                            st.session_state.selected_quest_name
                        )
                        st.session_state.level = nl; st.session_state.xp = nx
                        msg = "주문 해독 성공!"
                        if stat == "UPGRADE": msg = f"마법 숙련도 증가! ({cnt}회독)"
                        if g=="LEGEND": st.balloons(); st.success(f"👑 {msg} 전설적인 지식! (+{gain} 마력)")
                        else: st.success(f"{msg} (+{gain} 마력)")
                        time.sleep(1.5); del st.session_state.curr_ans; st.session_state.q_idx += 1; st.rerun()
                    else: st.error(f"주문 실패! 💥 {wrong_indices}번 룬이 잘못되었습니다.")

# 화면 4: 도감
elif st.session_state.page == 'collection':
    if st.button("🏠 중앙 홀로 귀환"): st.session_state.page = 'main'; st.rerun()
    st.header("📖 아카식 레코드 (도감)")
    
    my_cards = gm.get_collections(st.session_state.user_id)
    if not my_cards: st.info("기록된 지식이 없습니다.")
    else:
        quest_list = sorted(list(set([c.get('quest_name', '기타') for c in my_cards])))
        filter_q = st.multiselect("📂 서고 필터", quest_list, default=quest_list)
        filtered_cards = [c for c in my_cards if c.get('quest_name', '기타') in filter_q]
        
        st.caption(f"총 {len(filtered_cards)} 개의 지식이 기록됨")
        
        for c in filtered_cards:
            g = c.get('grade', 'NORMAL')
            cnt = c.get('count', 1)
            q_name = c.get('quest_name', 'Unknown')
            
            # 등급별 마법 테두리 색상
            if g == 'LEGEND': border_col = '#FFD700'; bg_col = 'rgba(255, 215, 0, 0.15)' # 골드
            elif g == 'RARE': border_col = '#00FFFF'; bg_col = 'rgba(0, 255, 255, 0.15)' # 시안(마법)
            else: border_col = '#cd7f32'; bg_col = 'rgba(205, 127, 50, 0.15)' # 브론즈(고대)
            
            st.markdown(f"""
                <div style="background:{bg_col}; border:2px solid {border_col}; border-radius:8px; padding:15px; margin-bottom:15px; box-shadow: 0 0 10px {border_col};">
                    <div style="display:flex; justify-content:space-between; margin-bottom:5px; font-family:'Cinzel Decorative', cursive;">
                        <span style="color:{border_col}; font-weight:bold;">{g} 등급</span>
                        <span style="color:#d4af37;">Lv.{cnt} 숙련</span>
                    </div>
                    <div style="font-size:1.1rem; line-height:1.6; margin-bottom:5px; color:#e8dcb5;">{c['card_text']}</div>
                    <div style="font-size:0.8rem; color:#aaa; text-align:right; font-style:italic;">출처: {q_name}</div>
                </div>
            """, unsafe_allow_html=True)
