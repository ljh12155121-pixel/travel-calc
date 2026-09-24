import streamlit as st
import json
import pandas as pd
import os
import math

# ==========================================
# 1. 페이지 설정 및 데이터 로드
# ==========================================
st.set_page_config(page_title="국외 출장 여비 계산기", page_icon="✈", layout="wide")

@st.cache_data
def load_data():
    file_path = "data.txt"
    if not os.path.exists(file_path):
        st.error(f"'{file_path}' 파일을 찾을 수 없습니다. 프로그램과 동일한 폴더에 위치시켜주세요.")
        st.stop()
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

app_data = load_data()
ALLOWANCE_TABLE = app_data["ALLOWANCE_TABLE"]
COUNTRIES_WITH_SPECIAL_CITIES = app_data["COUNTRIES_WITH_SPECIAL_CITIES"]
GRADE_B = app_data["GRADE_B_COUNTRIES"]
GRADE_C = app_data["GRADE_C_COUNTRIES"]
GRADE_D = app_data["GRADE_D_COUNTRIES"]
PREP_CATS = app_data["PREP_COMMON_CATEGORIES"]

# 국가 → 기본 등급 매핑
COUNTRY_DEFAULT_GRADE = {}
for c in GRADE_B: COUNTRY_DEFAULT_GRADE[c] = "나"
for c in GRADE_C: COUNTRY_DEFAULT_GRADE[c] = "다"
for c in GRADE_D: COUNTRY_DEFAULT_GRADE[c] = "라"
COUNTRY_DEFAULT_GRADE["홍콩"] = "가"
COUNTRY_DEFAULT_GRADE["싱가포르"] = "가"

ALL_COUNTRIES = sorted(set(GRADE_B + GRADE_C + GRADE_D))

def get_city_grade(city_display: str) -> str:
    if "가등급" in city_display: return "가"
    elif "나등급" in city_display: return "나"
    elif "다등급" in city_display: return "다"
    return None

def resolve_grade(country, city=""):
    if not country: return None
    if country in COUNTRIES_WITH_SPECIAL_CITIES and city:
        g = get_city_grade(city)
        if g: return g
    return COUNTRY_DEFAULT_GRADE.get(country)

# 숫자 입력 시 쉼표를 제거하고 실수형(float)으로 변환하는 함수
def clean_number_str(s):
    s = str(s).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

# ==========================================
# 2. 웹 UI 레이아웃 구성
# ==========================================
st.title("✈ 국외 출장 여비 계산기")
st.caption("공무원 여비 규정 [별표 4] 기준 (Streamlit 웹 버전)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("👤 직원 정보")
    name = st.text_input("성명", value="")
    position = st.selectbox("직급 선택", list(ALLOWANCE_TABLE.keys()))

    st.subheader("🌏 출장지 정보")
    country = st.selectbox("출장 국가", ALL_COUNTRIES)
    
    city = ""
    if country in COUNTRIES_WITH_SPECIAL_CITIES:
        city = st.selectbox("출장 도시", COUNTRIES_WITH_SPECIAL_CITIES[country])

    grade = resolve_grade(country, city)
    if grade:
        st.info(f"**적용 등급:** {grade}등급")
    else:
        st.warning("등급을 확인할 수 없습니다.")

    st.subheader("📅 출장 일정")
    c1, c2, c3 = st.columns(3)
    with c1: nights = st.number_input("숙박 박수", min_value=0, value=0)
    with c2: days = st.number_input("출장 일수", min_value=0, value=0)
    with c3: car_rental = st.number_input("차량임차 일수", min_value=0, value=0, help="해당 일비의 1/2만 지급됩니다.")

    st.subheader("🏨 숙박 정보")
    accom_type = st.radio("숙박비 유형", ["할인정액", "실비"], index=0, horizontal=True, help="할인정액은 실비의 85%로 계산됩니다.")

with col2:
    st.subheader("🍽 식사 공제")
    c4, c5, c6 = st.columns(3)
    with c4: breakfast = st.number_input("조식 횟수", min_value=0, value=0, help="1끼당 일 식비 1/3 공제")
    with c5: inflight = st.number_input("기내식 횟수", min_value=0, value=0, help="1끼당 일 식비 1/3 공제")
    with c6: other_meal = st.number_input("기타 공제", min_value=0, value=0)

    # ------------------------------------------
    # ✈ 항공운임 (천단위 쉼표 적용)
    # ------------------------------------------
    st.subheader("🛫 항공운임")
    
    def update_airfare():
        val = clean_number_str(st.session_state.airfare_input)
        st.session_state.airfare_input = f"{int(val):,}"

    if "airfare_input" not in st.session_state:
        st.session_state.airfare_input = "0"
        
    st.text_input("항공운임 (원화)", key="airfare_input", on_change=update_airfare)

    # ------------------------------------------
    # 💼 준비금
    # ------------------------------------------
    st.subheader("💼 준비금")
    st.caption("표 아래의 '+' 버튼을 눌러 항목을 추가하거나, 행을 선택해 'Delete' 키로 삭제할 수 있습니다.")
    
    if "prep_df" not in st.session_state:
        st.session_state.prep_df = pd.DataFrame([{"항목": "여행자보험료", "기타항목입력": "", "금액": "0", "통화": "KRW"}])
    
    config = {
        "항목": st.column_config.SelectboxColumn("항목", options=PREP_CATS, required=True),
        "기타항목입력": st.column_config.TextColumn("기타항목입력 (기타 선택시에만 반영)"),
        "금액": st.column_config.TextColumn("금액 (입력 시 자동 쉼표)"),
        "통화": st.column_config.SelectboxColumn("통화", options=["KRW", "USD"], default="KRW", required=True)
    }
    
    edited_prep = st.data_editor(
        st.session_state.prep_df, 
        column_config=config, 
        num_rows="dynamic", 
        use_container_width=True,
        hide_index=True,
        key="prep_editor"
    )

    needs_rerun = False
    for i, row in edited_prep.iterrows():
        # 1. 금액 쉼표 처리
        raw_str = str(row["금액"])
        if raw_str.strip() == "": raw_str = "0"
        val = clean_number_str(raw_str)
        fmt_val = f"{int(val):,}" if val % 1 == 0 else f"{val:,.1f}"
        if raw_str != fmt_val:
            edited_prep.at[i, "금액"] = fmt_val
            needs_rerun = True
            
        # 2. 기타 항목이 아닌데 내용이 있으면 자동 초기화 (막기)
        if row["항목"] != "기타" and row["기타항목입력"] != "":
            edited_prep.at[i, "기타항목입력"] = ""
            needs_rerun = True
            
    if needs_rerun:
        st.session_state.prep_df = edited_prep
        st.rerun()
    else:
        st.session_state.prep_df = edited_prep
    
    # ------------------------------------------
    # 💱 환율 (천단위 쉼표 적용)
    # ------------------------------------------
    st.subheader("💱 환율")
    
    def update_exchange():
        val = clean_number_str(st.session_state.exchange_input)
        st.session_state.exchange_input = f"{int(val):,}" if val % 1 == 0 else f"{val:,.1f}"

    if "exchange_input" not in st.session_state:
        st.session_state.exchange_input = "1,350"

    st.text_input("적용 환율 (원/달러)", key="exchange_input", on_change=update_exchange)

st.markdown("---")

# ==========================================
# 3. 계산 및 결과 출력 로직
# ==========================================
def truncate_1_decimal(value):
    return math.floor(value * 10) / 10

if st.button("📊 여비 계산하기", type="primary", use_container_width=True):
    airfare_krw = clean_number_str(st.session_state.airfare_input)
    exchange = clean_number_str(st.session_state.exchange_input)

    if car_rental > days:
        st.error("차량임차 일수는 출장 일수보다 클 수 없습니다.")
    else:
        rates = ALLOWANCE_TABLE[position][grade]
        
        # 1. 일비 계산 
        daily_rate = rates["일비"]
        full_daily_days = days - car_rental
        half_daily_days = car_rental
        calc_daily = daily_rate * full_daily_days + (daily_rate / 2) * half_daily_days
        total_daily = truncate_1_decimal(calc_daily)
        
        # 2. 숙박비 계산 
        if accom_type == "실비":
            per_night = rates["숙박비_상한"]
        else:
            per_night = rates["숙박비_할인"]
        calc_hotel = per_night * nights
        total_hotel = truncate_1_decimal(calc_hotel)
        
        # 3. 식비 계산 
        meal_rate = rates["식비"]
        total_meal_count = days * 3
        excluded_meal_count = breakfast + inflight + other_meal
        meal_count_after_exclusion = max(0, total_meal_count - excluded_meal_count)
        meal_unit = meal_rate / 3
        calc_meal = meal_unit * meal_count_after_exclusion
        total_meal = truncate_1_decimal(calc_meal)

        # 4. 준비금 취합
        prep_usd_total = 0.0
        prep_krw_total = 0.0
        prep_items_narrative = []
        
        for _, row in edited_prep.iterrows():
            amt = clean_number_str(row["금액"])
            if amt == 0: continue
            
            cat = row["항목"]
            if cat == "기타" and row["기타항목입력"]:
                cat = row["기타항목입력"]
                
            if row["통화"] == "USD":
                prep_usd_total += amt
                prep_items_narrative.append(f"({cat})${amt:,.1f}")
            else:
                prep_krw_total += amt
                prep_items_narrative.append(f"({cat}){amt:,.0f}원")

        prep_usd_total = truncate_1_decimal(prep_usd_total)

        # 5. 합계 계산 
        calc_total_usd = total_daily + total_hotel + total_meal + prep_usd_total
        total_usd = truncate_1_decimal(calc_total_usd)
        
        fixed_krw_total = airfare_krw + prep_krw_total
        total_krw = math.floor(total_usd * exchange + fixed_krw_total)

        # ====================
        # 결과 화면 출력
        # ====================
        st.header("📋 출장 여비 계산 결과")
        
        rc1, rc2, rc3 = st.columns(3)
        rc1.metric("총 합산 금액 (환율적용)", f"₩{total_krw:,.0f}")
        rc2.metric("달러 ($)", f"${total_usd:,.1f}")
        rc3.metric("원화 (₩)", f"₩{fixed_krw_total:,.0f}")

        st.subheader("📝 산출내역 (복사 가능)")
        
        lines = ["※ 출장경비 산출내역"]
        if car_rental > 0:
            lines.append(f"-일비 : 출장일수({days}일) 중 일반 {full_daily_days}일 정상 지급, 차량임차 {half_daily_days}일 1/2 지급 → ${total_daily:,.1f}")
        else:
            lines.append(f"-일비 : 출장일수({days}일)에 따라 지급 → ${total_daily:,.1f}")

        excluded_parts = []
        if breakfast > 0: excluded_parts.append(f"호텔 조식 {breakfast}식")
        if inflight > 0: excluded_parts.append(f"기내식 {inflight}식")
        if other_meal > 0: excluded_parts.append(f"기타 {other_meal}식")

        if excluded_parts:
            lines.append(f"-식비 : 총 {meal_count_after_exclusion}식 청구(총 {total_meal_count}식 중 {', '.join(excluded_parts)} 제외) → ${total_meal:,.1f}")
        else:
            lines.append(f"-식비 : 총 {total_meal_count}식 청구 → ${total_meal:,.1f}")

        lines.append(f"-숙박비 : 총 {nights}박 청구 ({accom_type}) → ${total_hotel:,.1f}")

        if prep_items_narrative:
            lines.append(f"-준비금 : {', '.join(prep_items_narrative)} 청구")

        if airfare_krw > 0:
            lines.append(f"-운임료 : (항공){airfare_krw:,.0f}원 청구")

        narrative_text = "\n".join(lines)
        st.code(narrative_text, language="text")

        st.subheader("📊 항목별 상세 테이블")
        df_result = pd.DataFrame({
            "성명/출장지": [f"{name}\n({country}{' / ' + city if city else ''})"],
            "계(KRW)": [f"₩{total_krw:,.0f}"],
            "항공운임": [f"₩{airfare_krw:,.0f}"],
            "일비": [f"${total_daily:,.1f}"],
            "식비": [f"${total_meal:,.1f}"],
            "숙박비": [f"${total_hotel:,.1f}"],
            "준비금 및 기타": [", ".join(prep_items_narrative) if prep_items_narrative else "-"]
        })
        st.dataframe(df_result, hide_index=True)