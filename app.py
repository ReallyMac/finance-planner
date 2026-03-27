import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Grok Holistic Finance Planner", layout="wide", page_icon="🧬")

st.title("🧬 Grok Holistic Finance Planner")
st.caption("Investments • Taxes • Retirement • Estate + Roth Conversions + Sequence of Returns Risk")

# ====================== SIDEBAR INPUTS ======================
st.sidebar.header("Your Profile")
age = st.sidebar.number_input("Current Age", 25, 100, 45)
retirement_age = st.sidebar.number_input("Retirement Age", age + 1, 100, 65)
filing_status = st.sidebar.selectbox("Filing Status", ["Single", "Married Filing Jointly"])
state = st.sidebar.text_input("State", "Illinois")

# Assets & Goals
st.sidebar.header("Current Balances ($)")
trad_ira = st.sidebar.number_input("Traditional IRA / 401(k)", 0, 5000000, 500000)
roth_ira = st.sidebar.number_input("Roth IRA", 0, 5000000, 100000)
taxable = st.sidebar.number_input("Taxable Brokerage", 0, 5000000, 200000)

annual_income = st.sidebar.number_input("Current Annual Income", 0, 1000000, 150000)
annual_spending = st.sidebar.number_input("Desired Annual Retirement Spending (today's $)", 0, 500000, 80000)
annual_savings = st.sidebar.number_input("Annual Savings ($/yr)", 0, 1000000, 30000)
inflation = st.sidebar.slider("Inflation Rate (%)", 1.0, 5.0, 3.0) / 100
stock_allocation = st.sidebar.slider("Stock Allocation (%)", 0, 100, 60)

# ====================== HELPER FUNCTIONS ======================
def federal_tax(income: float, status: str) -> float:
    """2026 Federal brackets (simplified)"""
    if status == "Single":
        brackets = [12400, 50400, 105700, 201775, 256225, 640600]
        rates = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    else:
        brackets = [24800, 100800, 211400, 403550, 512450, 768700]
        rates = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    tax = 0.0
    prev = 0.0
    for b, r in zip(brackets + [float('inf')], rates):
        tax += max(0, min(income, b) - prev) * r
        prev = b
        if income <= b: break
    return tax

def il_tax(income: float) -> float:
    return income * 0.0495

def roth_conversion_sim(trad, roth, annual_convert, years_to_retire, growth=0.07, tax_rate=0.22):
    df = pd.DataFrame(index=range(1, years_to_retire + 1), columns=["Trad", "Roth", "Tax Paid", "Cumulative Tax"])
    t, r, cum_tax = trad, roth, 0.0
    for y in range(1, years_to_retire + 1):
        convert = min(annual_convert, t)
        tax_this_year = convert * tax_rate
        t = (t - convert) * (1 + growth)
        r = (r + convert) * (1 + growth)
        cum_tax += tax_this_year
        df.loc[y] = [round(t, 2), round(r, 2), round(tax_this_year, 2), round(cum_tax, 2)]
    return df

def monte_carlo_sor(portfolio, years, withdrawal, mean_return=0.07, std_return=0.15, n_sims=1000, inflation_rate=0.03):
    success = 0
    paths = []
    for _ in range(n_sims):
        balance = portfolio
        path = [balance]
        for y in range(years):
            ret = np.random.normal(mean_return, std_return)
            balance = balance * (1 + ret) - withdrawal * (1 + inflation_rate) ** y
            path.append(max(balance, 0))
            if balance <= 0: break
        else:
            success += 1
        paths.append(path[:years + 1])
    success_rate = success / n_sims * 100
    paths = np.array(paths)
    percentiles = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
    return success_rate, percentiles

# ====================== TABS ======================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📊 Dashboard", "💼 Investments", "🧾 Taxes", "🔄 Roth Conversion", "🏖️ Retirement", "📉 Sequence of Returns", "🏛️ Estate Planning"])

with tab1:
    st.subheader("Quick Snapshot")
    years_to_ret = retirement_age - age
    st.metric("Years to Retirement", years_to_ret)
    total_assets = trad_ira + roth_ira + taxable
    st.metric("Total Investable Assets", f"${total_assets:,.0f}")
    projected_portfolio = total_assets * (1.07 ** years_to_ret) + annual_savings * (((1.07 ** years_to_ret) - 1) / 0.07)
    st.metric("Projected Portfolio at Retirement (7% growth)", f"${projected_portfolio:,.0f}")

with tab2:
    st.subheader("Investment Projections")
    blended_return = stock_allocation * 0.07 + (100 - stock_allocation) * 0.03
    st.write(f"Assumed blended return: **{blended_return:.1f}%**")
    st.progress(stock_allocation / 100, text=f"Stock Allocation: {stock_allocation}%")

with tab3:
    st.subheader("2026 Tax Estimator")
    taxable_income = st.number_input("Estimated Taxable Income (pre-conversion)", 0, 1000000, annual_income)
    fed_tax = federal_tax(taxable_income, filing_status)
    state_tax = il_tax(taxable_income)
    st.write(f"**Federal Tax:** ${fed_tax:,.0f}")
    st.write(f"**Illinois State Tax:** ${state_tax:,.0f}")
    st.write(f"**Total Tax:** ${fed_tax + state_tax:,.0f}")

with tab4:
    st.subheader("Roth Conversion Planner")
    years_convert = st.slider("Years of Conversions Before Retirement", 1, 20, 5)
    annual_convert_amt = st.number_input("Annual Conversion Amount", 0, 500000, 50000)
    assumed_tax_rate = st.slider("Assumed Marginal Tax Rate on Conversion (%)", 10, 37, 22) / 100
    df_roth = roth_conversion_sim(trad_ira, roth_ira, annual_convert_amt, years_convert, tax_rate=assumed_tax_rate)
    st.dataframe(df_roth.style.format("${:,.0f}"), use_container_width=True)
    st.caption("Taxes assumed paid from non-retirement funds. Roth grows tax-free.")

with tab5:
    st.subheader("Retirement Projection")
    safe_withdrawal = projected_portfolio * 0.04
    st.metric("Safe Annual Withdrawal (4% rule)", f"${safe_withdrawal:,.0f}")
    st.write(f"Compared to your goal: **${annual_spending:,.0f}** (inflation-adjusted)")

with tab6:
    st.subheader("Sequence of Returns Risk Simulator")
    years_retired = st.number_input("Years in Retirement", 10, 50, 30)
    withdrawal_goal = st.number_input("Annual Withdrawal Goal (today's $)", 40000, 500000, int(annual_spending))
    success_rate, percentiles = monte_carlo_sor(
        projected_portfolio, years_retired, withdrawal_goal, inflation_rate=inflation
    )
    st.metric("Success Rate (portfolio lasts full retirement)", f"{success_rate:.1f}%")
    
    fig = make_subplots(rows=1, cols=1)
    years_list = list(range(years_retired + 1))
    fig.add_trace(go.Scatter(x=years_list, y=percentiles[4], mode='lines', name='95th percentile', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=years_list, y=percentiles[3], mode='lines', name='75th', fill='tonexty', line=dict(color='lightgreen')))
    fig.add_trace(go.Scatter(x=years_list, y=percentiles[2], mode='lines', name='Median', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=years_list, y=percentiles[1], mode='lines', name='25th', fill='tonexty', line=dict(color='orange')))
    fig.add_trace(go.Scatter(x=years_list, y=percentiles[0], mode='lines', name='5th percentile', line=dict(color='red')))
    fig.update_layout(title="Monte Carlo Portfolio Paths", xaxis_title="Years in Retirement", yaxis_title="Portfolio Value ($)")
    st.plotly_chart(fig, use_container_width=True)

with tab7:
    st.subheader("Estate Planning Snapshot")
    estate_exemption = 13610000 if filing_status == "Single" else 27220000
    st.write(f"2026 Federal Estate Tax Exemption: ≈ **${estate_exemption:,.0f}**")
    projected_estate = projected_portfolio * (1.05 ** 20)
    if projected_estate > estate_exemption:
        estate_tax = (projected_estate - estate_exemption) * 0.40
        st.metric("Estimated Federal Estate Tax Owed", f"${estate_tax:,.0f}")
    else:
        st.success("✅ No federal estate tax expected")
    st.write("Heirs receive (pre-tax):", f"${projected_estate:,.0f}")

st.divider()
st.caption("Built live by Grok • Educational prototype only • Not financial advice")
