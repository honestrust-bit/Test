import streamlit as st
import sqlite3
import random
import time
import pandas as pd
from kiwipiepy import Kiwi

# --------------------------------------------------------------------------
# 1. 게임 시스템 & DB 관리 (Backend)
# --------------------------------------------------------------------------
class GameSystem:
    def __init__(self, db_name="memory_guardians.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # 유저 테이블
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY, 
            password TEXT,
            level INTEGER DEFAULT 1, 
            xp INTEGER DEFAULT 0,
            title TEXT DEFAULT '견습 가디언'
        )''')
        # 수집 테이블
        cursor.execute('''CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            card_text TEXT,
            grade TEXT, -- Normal, Rare, Legend
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        # 업적 테이블
        cursor.execute('''CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            code TEXT,
            unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        self.conn.commit()

    # --- 회원 관리 ---
    def login(self, user_id, password):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=? AND password=?", (user_id, password))
        return cursor.fetchone()

    def register(self, user_id, password):
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO users (user_id, password) VALUES (?, ?)", (user_id, password))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    # --- 게임 로직 (보상 처리) ---
    def process_reward(self, user_id, card_text):
        cursor = self.conn.cursor()
        
        # 1. 등급 랜덤 결정 (가챠 시스템)
        rand_val = random.random()
        if rand_val < 0.05: grade = "LEGEND"    # 5% 확률
        elif rand_val < 0.20: grade = "RARE"    # 15% 확률
        else: grade = "NORMAL"                  # 80% 확률
        
        # 2. 경험치 계산
        xp_gain = 50 if grade == "LEGEND" else 30 if grade == "RARE" else 10
        
        # 3. 유저 정보 업데이트
        cursor.execute("SELECT level, xp FROM users WHERE user_id=?", (user_id,))
        lv, xp = cursor.fetchone()
        new_xp = xp + xp_gain
        req_xp = lv * 100
        
        leveled_up = False
        if new_xp >= req_xp:
            lv += 1
            new_xp -= req_xp
            leveled_up = True
            
        cursor.execute("UPDATE users SET level=?, xp=? WHERE user_id=?", (lv, new_xp, user_id))
        
        # 4. 카드 수집 (중복 저장 허용 -> 같은 카드라도 등급 다를 수 있음)
        cursor.execute("INSERT INTO collections (user_id, card_text, grade) VALUES (?, ?, ?)", 
                       (user_id, card_text, grade))
        
        self.conn.commit()
        return grade, leveled_up, xp_gain

    # --- 데이터 조회 ---
    def get_user_info(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return cursor.fetchone()

    def get_collections(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT card_text, grade, collected_at FROM collections WHERE user_id=? ORDER BY id DESC", (user_id,))
        return cursor.fetchall()

# --------------------------------------------------------------------------
# 2. UI 스타일링 (CSS)
# --------------------------------------------------------------------------
def apply_style():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Gowun+Dodum&display=swap');
        
        .stApp { background-color: #121212; color: #f0f0f0; font-family: 'Gowun Dodum', sans-serif; }
        h1, h2, h3 { font-family: 'Black Han Sans', sans-serif; color: #FFD700; }
        
        /* 카드 스타일 */
        .card-box {
            padding: 15px; border-radius: 10px; margin-bottom: 10px;
            color: #000; font-weight: bold;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            transition: transform 0.2s;
        }
        .card-box:hover { transform: scale(1.02); }
        
        .grade-NORMAL { background: linear-gradient(to right, #d3cce3, #e9e4f0); border-left: 5px solid #a1a1a1; }
        .grade-RARE { background: linear-gradient(to right, #89f7fe, #66a6ff); border-left: 5px solid #0000ff; }
        .grade-LEGEND { background: linear-gradient(to right, #f2994a, #f2c94c); border-left: 5px solid #FFD700; box-shadow: 0 0 15px #FFD700; }
        
        /* 아바타 */
        .avatar-box { text-align: center; padding: 20px; background: #1e1e1e; border-radius: 15px; border: 1px solid #333; }
        .avatar-icon { font-size: 80px; animation: float 3s ease-in-out infinite; }
        
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }
        </style>
    """, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 3. 메인 앱 로직
# --------------------------------------------------------------------------
st.set_page_config(page_title="메모리 가디언즈", page_icon="🛡️", layout="wide")
apply_style()
gm = GameSystem()

# Kiwi 로드
@st.cache_resource
def load_kiwi():
    return Kiwi()

# 세션 초기화
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

# ==========================================
# [로그인 화면]
# ==========================================
if st.session_state.user_id is None:
    st.title("🛡️ 메모리 가디언즈")
    st.markdown("지식의 던전을 탐험하고 전설의 카드를 수집하세요.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("로그인")
        l_id = st.text_input("아이디", key="l_id")
        l_pw = st.text_input("비밀번호", type="password", key="l_pw")
        if st.button("접속하기"):
            user = gm.login(l_id, l_pw)
            if user:
                st.session_state.user_id = l_id
                st.success(f"{l_id} 가디언님, 환영합니다!")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 틀렸습니다.")
                
    with col2:
        st.subheader("회원가입")
        r_id = st.text_input("새 아이디", key="r_id")
        r_pw = st.text_input("새 비밀번호", type="password", key="r_pw")
        if st.button("가입하기"):
            if gm.register(r_id, r_pw):
                st.success("가입 완료! 왼쪽에서 로그인해주세요.")
            else:
                st.error("이미 존재하는 아이디입니다.")

# ==========================================
# [메인 게임 화면]
# ==========================================
else:
    # 유저 최신 정보 조회
    u_data = gm.get_user_info(st.session_state.user_id)
    u_id, _, u_lv, u_xp, u_title = u_data
    
    # 아바타 결정 로직
    avatar = "🥚" if u_lv < 5 else "🐣" if u_lv < 10 else "🦅" if u_lv < 20 else "🐲"
    
    # [사이드바] 내 정보
    with st.sidebar:
        st.markdown(f"""
        <div class="avatar-box">
            <div class="avatar-icon">{avatar}</div>
            <h2>Lv.{u_lv} {u_id}</h2>
            <p>{u_title}</p>
        </div>
        """, unsafe_allow_html=True)
        
        req_xp = u_lv * 100
        st.write(f"**EXP**: {u_xp} / {req_xp}")
        st.progress(min(u_xp / req_xp, 1.0))
        
        if st.button("로그아웃", type="primary"):
            st.session_state.user_id = None
            st.rerun()

    # [메인 탭]
    tab1, tab2 = st.tabs(["⚔️ 던전 (학습)", "📖 내 도감 (Collection)"])

    # --- 탭 1: 던전 ---
    with tab1:
        st.header("💀 지식의 던전")
        uploaded_file = st.file_uploader("던전 생성 주문서 (.txt파일)", type=['txt'])
        
        # 파일이 있으면 문제 생성
        if uploaded_file:
            text_data = uploaded_file.getvalue().decode("utf-8")
            kiwi = load_kiwi()
            
            # 세션에 문제 저장 (새로고침 방지)
            if 'dungeon_sents' not in st.session_state:
                st.session_state.dungeon_sents = [s.text for s in kiwi.split_into_sents(text_data) if len(s.text)>10]
                st.session_state.q_idx = 0
            
            # 모든 문제를 다 풀었으면
            if not st.session_state.dungeon_sents:
                 st.info("이 파일의 모든 몬스터를 처치했습니다! 새로운 파일을 올려주세요.")
            else:
                # 현재 문제 출제
                if st.session_state.q_idx < len(st.session_state.dungeon_sents):
                    curr_sent = st.session_state.dungeon_sents[st.session_state.q_idx]
                    
                    # 빈칸 뚫기
                    tokens = kiwi.tokenize(curr_sent)
                    nouns = [t.form for t in tokens if t.tag.startswith('N') and len(t.form)>1]
                    
                    if not nouns: # 명사가 없으면 다음 문장으로
                        st.session_state.q_idx += 1
                        st.rerun()
                    
                    answer = random.choice(nouns)
                    q_text = curr_sent.replace(answer, "______")
                    
                    st.info(f"몬스터 출현! (진행도: {st.session_state.q_idx + 1}/{len(st.session_state.dungeon_sents)})")
                    st.markdown(f"### Q. {q_text}")
                    
                    with st.form("battle_form"):
                        user_ans = st.text_input("공격 주문(정답) 입력")
                        atk_btn = st.form_submit_button("⚔️ 공격하기")
                        
                        if atk_btn:
                            if answer in user_ans:
                                # 보상 지급
                                grade, is_lvup, gain_xp = gm.process_reward(u_id, curr_sent)
                                
                                # 연출
                                if grade == "LEGEND":
                                    st.balloons()
                                    st.success(f"👑 대박! 전설의 카드를 얻었습니다! (+{gain_xp} XP)")
                                elif grade == "RARE":
                                    st.success(f"✨ 희귀한 카드 발견! (+{gain_xp} XP)")
                                else:
                                    st.info(f"🛡️ 일반 카드 획득. (+{gain_xp} XP)")
                                
                                if is_lvup: st.toast(f"🎉 레벨 업! Lv.{u_lv+1} 달성!", icon="🆙")
                                
                                # 다음 문제로 이동
                                time.sleep(1.5)
                                st.session_state.q_idx += 1
                                st.rerun()
                            else:
                                st.error(f"빗나갔습니다! 약점은 '{answer}'였습니다.")
                else:
                    st.success("던전 클리어! 새로운 파일을 올려주세요.")
                    if st.button("던전 초기화"):
                        del st.session_state.dungeon_sents
                        st.rerun()

    # --- 탭 2: 도감 ---
    with tab2:
        st.header("📖 수집한 카드 도감")
        my_cards = gm.get_collections(u_id)
        
        if not my_cards:
            st.warning("아직 수집한 카드가 없습니다. 던전에서 몬스터를 사냥하세요!")
        else:
            # 통계 표시
            l_cnt = sum(1 for c in my_cards if c[1]=="LEGEND")
            r_cnt = sum(1 for c in my_cards if c[1]=="RARE")
            st.write(f"총 {len(my_cards)}장 (👑전설: {l_cnt} / ✨희귀: {r_cnt})")
            
            # 카드 리스트 출력
            for text, grade, date in my_cards:
                st.markdown(f"""
                <div class="card-box grade-{grade}">
                    <div style="font-size:0.8em; opacity:0.7;">[{grade}] {date[:16]}</div>
                    <div style="margin-top:5px;">{text}</div>
                </div>
                """, unsafe_allow_html=True)

