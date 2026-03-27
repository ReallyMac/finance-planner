import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime

st.set_page_config(page_title="Grok Holistic Finance Planner v4", layout="wide", page_icon="🧬")

# ====================== PASSWORD PROTECTION ======================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Grok Holistic Finance Planner v4")
    st.caption("Professional Financial Planning App")
    password = st.text_input("Enter access password", type="password")
    if st.button("Unlock App"):
        if password == "grokv4":  # ← CHANGE THIS TO YOUR OWN PASSWORD
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password – try again")
    st.stop()

# ====================== TITLE ======================
st.title("🧬 Grok Holistic Finance Planner **v4**")
st.caption("Password-protected • Multi-scenario • CSV exports • Live market data • 2026 rules")

# ====================== LIVE MARKET CONTEXT ======================
st.sidebar.header("📡 Live Market Snapshot")
try:
    spx = yf.Ticker("^GSPC").history(period="5d")["Close"].iloc[-1]
    agg = yf.Ticker("AGG").history(period="5d")["Close"].iloc[-1]  # iShares Core U.S. Aggregate Bond
    st.sidebar.metric("S&P 500 (today)", f"${spx:,.0f}")
    st.sidebar.metric("Bond ETF (AGG)", f"${agg:,.2f}")
except:
    st.sidebar.caption("Live data temporarily unavailable")

# ====================== SIDEBAR INPUTS ======================
st.sidebar.header("Scenario")
scenario = st.sidebar.selectbox("Choose Scenario", ["Base", "Optimistic", "Conservative"])
scenario_adj = {"Base": (1.0, 1.0), "Optimistic": (1.15, 0.85), "Conservative": (0.85, 1.25)}

st.sidebar.header("Your Profile")
age = st.sidebar.number_input("Current Age", 25, 100, 45)
retirement_age = st.sidebar.number_input("Retirement Age", age + 1, 100, 65)
filing_status = st.sidebar.selectbox("Filing Status", ["Single", "Married Filing Jointly"])

st.sidebar.header("Assets & Income")
trad_ira = st.sidebar.number_input("Traditional IRA / 401(k)", 0, 5000000, 500000)
roth_ira = st.sidebar.number_input("Roth IRA", 0, 5000000, 100000)
taxable = st.sidebar.number_input("Taxable Brokerage", 0, 5000000, 200000)
annual_income = st.sidebar.number_input("Current Annual Income", 0, 1000000, 150000)
ss_annual = st.sidebar.number_input("Estimated Annual Social Security (today's $)", 0, 50000, 20000)

st.sidebar.header("Goals & Assumptions")
annual_spending = st.sidebar.number_input("Desired Annual Retirement Spending (today's $)", 0, 500000, 80000)
annual_savings = st.sidebar.number_input("Annual Savings ($/yr)", 0, 1000000, 30000)
inflation = st.sidebar.slider("Inflation (%)", 1.0, 5.0, 3.0) / 100
std_deduction = st.sidebar.number_input("2026 Standard Deduction", value=15000 if filing_status == "Single" else 30000)

st.sidebar.header("Investment Assumptions")
stock_alloc = st.sidebar.slider("Stock Allocation (%)", 0, 100, 60)
stock_return = st.sidebar.slider("Expected Stock Return (%)", 4.0, 12.0, 8.0) / 100
bond_return = st.sidebar.slider("Expected Bond Return (%)", 1.0, 6.0, 3.0) / 100
stock_vol = st.sidebar.slider("Stock Volatility (%)", 10.0, 25.0, 15.0) / 100
bond_vol = st.sidebar.slider("Bond Volatility (%)", 2.0, 8.0, 4.0) / 100

# Apply scenario multiplier
ret_mult, vol_mult = scenario_adj[scenario]
blended_return = (stock_alloc/100 * stock_return + (1 - stock_alloc/100) * bond_return) * ret_mult
blended_vol = (stock_alloc/100 * stock_vol + (1 - stock_alloc/100) * bond_vol) * vol_mult

# ====================== PRE-COMPUTE ======================
years_to_ret = retirement_age - age
total_assets = trad_ira + roth_ira + taxable
projected_portfolio = total_assets * (1 + blended_return) ** years_to_ret + annual_savings * (((1 + blended_return) ** years_to_ret - 1) / blended_return)
fi_number = annual_spending * 25  # classic 4% rule

# ====================== HELPER FUNCTIONS ======================
def federal_tax(income: float, status: str, std_ded: float) -> float:
    taxable = max(0, income - std_ded)
    if status == "Single":
        brackets = [0, 12400, 50400, 105700, 201775, 256225, 640600, float('inf')]
        rates = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    else:
        brackets = [0, 24800, 100800, 211400, 403550, 512450, 768700, float('inf')]
        rates = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    tax = 0.0
    prev = 0.0
    for b, r in zip(brackets[1:], rates):
        tax += max(0, min(taxable, b) - prev) * r
        prev = b
        if taxable <= b: break
    return tax

def il_tax(income: float) -> float:
    return max(0, income - 2850) * 0.0495

def calculate_rmd(a: int, trad_balance: float) -> float:
    if a < 73: return 0.0
    divisors = {73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1, 80: 20.2,
                81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4, 88: 13.7,
                89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8, 93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4,
                97: 7.9, 98: 7.4, 99: 7.0, 100: 6.5}
    divisor = divisors.get(a, 6.5)
    return trad_balance / divisor

def monte_carlo_sor(portfolio, years, withdrawal, mean_return, std_return, n_sims=1000, inflation_rate=0.03):
    np.random.seed(42)
    success = 0
    paths = []
    for _ in range(n_sims):
        balance = float(portfolio)
        path = [balance]
        for y in range(years):
            ret = np.random.normal(mean_return, std_return)
            balance = balance * (1 + ret) - withdrawal * (1 + inflation_rate) ** y
            path.append(max(balance, 0))
            if balance <= 0: break
        else:
            success += 1
        full_path = path + [0.0] * (years + 1 - len(path))
        paths.append(full_path)
    success_rate = success / n_sims * 100
    paths_arr = np.array(paths)
    percentiles = np.percentile(paths_arr, [5, 25, 50, 75, 95], axis=0)
    return success_rate, percentiles, paths_arr

def year_by_year_projection():
    df = pd.DataFrame(index=range(age, retirement_age + 40), columns=["Age", "Trad", "Roth", "Taxable", "Total Portfolio", "Withdrawal", "RMD", "Tax", "Net Cash Flow"])
    trad_b = float(trad_ira)
    roth_b = float(roth_ira)
    tax_b = float(taxable)
    for a in range(age, retirement_age + 40):
        if a < retirement_age:
            growth = (1 + blended_return)
            trad_b *= growth
            roth_b *= growth
            tax_b = tax_b * growth + annual_savings
            wdraw = rmd = total_tax = 0.0
        else:
            wdraw = annual_spending * (1 + inflation) ** (a - retirement_age)
            rmd = calculate_rmd(a, trad_b) if trad_b > 0 else 0.0
            taxable_inc = annual_income + rmd + ss_annual
            fed = federal_tax(taxable_inc, filing_status, std_deduction)
            state_t = il_tax(taxable_inc)
            total_tax = fed + state_t
            trad_b = max(0.0, trad_b - rmd)
            # Withdraw from taxable first, then trad, then roth (common strategy)
            remaining = wdraw
            tax_b = max(0.0, tax_b - remaining)
            remaining = max(0.0, remaining - (tax_b + remaining))  # simplistic
            trad_b = max(0.0, trad_b - remaining)
            roth_b = max(0.0, roth_b - max(0, remaining - trad_b))
            trad_b *= (1 + blended_return)
            roth_b *= (1 + blended_return)
            tax_b *= (1 + blended_return)
        total_port = trad_b + roth_b + tax_b
        net_cf = annual_savings if a < retirement_age else (ss_annual - wdraw - total_tax)
        df.loc[a] = [a, round(trad_b, 0), round(roth_b, 0), round(tax_b, 0), round(total_port, 0),
                     round(wdraw, 0), round(rmd, 0), round(total_tax, 0), round(net_cf, 0)]
    return df

# ====================== TABS ======================
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "📊 Dashboard", "💼 Investments", "🧾 Taxes", "🔄 Roth", "🏖️ Retirement",
    "📉 SOR", "📅 Year-by-Year", "🔀 Scenarios", "🏛️ Estate"
])

with tab1:
    st.subheader("Quick Snapshot")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Years to Retirement", years_to_ret)
    col2.metric("Total Assets", f"${total_assets:,.0f}")
    col3.metric("Projected Portfolio", f"${projected_portfolio:,.0f}")
    col4.metric("FI Number (25× rule)", f"${fi_number:,.0f}")
    st.progress(stock_alloc / 100, text=f"{scenario} Scenario • Blended Return: {blended_return*100:.1f}% • Vol: {blended_vol*100:.1f}%")
    if st.button("📤 Export Dashboard CSV"):
        st.download_button("Download CSV", pd.DataFrame({"Metric": ["Projected Portfolio", "FI Number"], "Value": [projected_portfolio, fi_number]}).to_csv(index=False), "dashboard.csv", "text/csv")

with tab2:
    st.subheader("Investment Breakdown")
    fig_pie = go.Figure(data=[go.Pie(labels=["Stocks", "Bonds"], values=[stock_alloc, 100 - stock_alloc], hole=0.4)])
    st.plotly_chart(fig_pie, use_container_width=True)

with tab3:
    st.subheader("2026 Tax Estimator")
    taxable_income = st.number_input("Pre-deduction Income", 0, 1000000, annual_income)
    fed = federal_tax(taxable_income, filing_status, std_deduction)
    state_t = il_tax(taxable_income)
    st.metric("Federal Tax", f"${fed:,.0f}")
    st.metric("Illinois Tax", f"${state_t:,.0f}")
    st.metric("Total Tax", f"${fed + state_t:,.0f}")

with tab4:
    st.subheader("Roth Conversion Planner")
    years_convert = st.slider("Conversion Years", 1, 15, 5)
    annual_convert = st.number_input("Annual Conversion Amount", 0, 500000, 50000)
    tax_rate_conv = st.slider("Marginal Tax Rate on Conversion (%)", 10, 37, 22) / 100
    trad_no = trad_ira * (1 + blended_return) ** years_convert
    roth_no = roth_ira * (1 + blended_return) ** years_convert
    trad_yes = max(0, trad_ira - annual_convert * years_convert) * (1 + blended_return) ** years_convert
    roth_yes = (roth_ira + annual_convert * years_convert) * (1 + blended_return) ** years_convert
    col_a, col_b = st.columns(2)
    col_a.metric("Without Conversion", f"${trad_no + roth_no:,.0f}")
    col_b.metric("With Conversion", f"${trad_yes + roth_yes:,.0f}")
    if st.button("📤 Export Roth CSV"):
        st.download_button("Download Roth Comparison", pd.DataFrame({"Scenario": ["Without", "With"], "Value": [trad_no + roth_no, trad_yes + roth_yes]}).to_csv(index=False), "roth_comparison.csv", "text/csv")

with tab5:
    st.subheader("Retirement & RMD")
    safe_wd = projected_portfolio * 0.04
    st.metric("4% Safe Withdrawal", f"${safe_wd:,.0f}")
    if retirement_age >= 73:
        rmd_example = calculate_rmd(retirement_age, trad_ira)
        st.metric(f"First RMD (age {retirement_age})", f"${rmd_example:,.0f}")

with tab6:
    st.subheader("Sequence of Returns Risk")
    years_ret = st.number_input("Retirement Length (years)", 10, 50, 30)
    wd_goal = st.number_input("Annual Withdrawal Goal", 40000, 500000, int(annual_spending))
    success_rate, percentiles, _ = monte_carlo_sor(projected_portfolio, years_ret, wd_goal, blended_return, blended_vol, inflation_rate=inflation)
    st.metric("Success Rate", f"{success_rate:.1f}%")
    fig_sor = make_subplots(rows=1, cols=1)
    years_list = list(range(years_ret + 1))
    fig_sor.add_trace(go.Scatter(x=years_list, y=percentiles[4], mode='lines', name='95th', line=dict(color='green')))
    fig_sor.add_trace(go.Scatter(x=years_list, y=percentiles[3], mode='lines', name='75th', fill='tonexty', line=dict(color='lightgreen')))
    fig_sor.add_trace(go.Scatter(x=years_list, y=percentiles[2], mode='lines', name='Median', line=dict(color='blue')))
    fig_sor.add_trace(go.Scatter(x=years_list, y=percentiles[1], mode='lines', name='25th', fill='tonexty', line=dict(color='orange')))
    fig_sor.add_trace(go.Scatter(x=years_list, y=percentiles[0], mode='lines', name='5th', line=dict(color='red')))
    fig_sor.update_layout(title=f"{scenario} Scenario Monte Carlo (1,000 paths)", xaxis_title="Years", yaxis_title="Portfolio Value ($)")
    st.plotly_chart(fig_sor, use_container_width=True)

with tab7:
    st.subheader("📅 Year-by-Year Projections")
    df_proj = year_by_year_projection()
    st.dataframe(df_proj.style.format("${:,.0f}"), use_container_width=True)
    if st.button("📤 Export Projections CSV"):
        st.download_button("Download Full Projections", df_proj.to_csv(), "year_by_year.csv", "text/csv")
    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(x=df_proj.index, y=df_proj["Total Portfolio"], mode="lines", name="Portfolio"))
    st.plotly_chart(fig_proj, use_container_width=True)

with tab8:
    st.subheader("🔀 Multi-Scenario Comparison")
    scenarios = ["Base", "Optimistic", "Conservative"]
    results = []
    for sc in scenarios:
        ret_m, vol_m = scenario_adj[sc]
        r = (stock_alloc/100 * stock_return + (1 - stock_alloc/100) * bond_return) * ret_m
        p = total_assets * (1 + r) ** years_to_ret + annual_savings * (((1 + r) ** years_to_ret - 1) / r)
        sr, _, _ = monte_carlo_sor(p, 30, annual_spending, r, blended_vol * vol_m, inflation_rate=inflation)
        results.append([sc, f"${p:,.0f}", f"{sr:.1f}%"])
    comp_df = pd.DataFrame(results, columns=["Scenario", "Projected Portfolio", "Success Rate (30 yrs)"])
    st.dataframe(comp_df.style.format({"Projected Portfolio": "${:,.0f}", "Success Rate (30 yrs)": "{:.1f}%"}), use_container_width=True)

with tab9:
    st.subheader("Estate Planning Snapshot")
    exemption = 15000000 if filing_status == "Single" else 30000000
    projected_estate = projected_portfolio * (1.05 ** 20)
    if projected_estate > exemption:
        estate_tax = (projected_estate - exemption) * 0.40
        st.metric("Est. Federal Estate Tax", f"${estate_tax:,.0f}")
    else:
        st.success("✅ No federal estate tax expected")

st.divider()
st.caption("✅ v4 shipped • Built live by Grok • Educational prototype only • Change password in code • Refresh after GitHub push")
