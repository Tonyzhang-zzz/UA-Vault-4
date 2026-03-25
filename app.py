import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(
    page_title="UA Creative Cohort Analysis", 
    layout="wide",
    # 你甚至可以用这个 JPG 作为浏览器的 Tab Icon (Favicon)
    page_icon="icon.jpg" 
)

# ==========================================
# 主页面标题区域 (调整为与 Icon 联动)
# ==========================================
st.title("📊 UA 游戏素材生命周期与同期群看板 (月度版)")
st.markdown("监控大盘的新老素材消耗结构与各【素材类型】的接力健康度。")


# ==========================================
# 侧边栏：Icon 装饰与数据上传
# ==========================================

# --- [新加入的美术装饰代码] ---
# 检查 Icon 文件是否存在，避免因文件丢失导致工具崩溃
if os.path.exists("icon.jpg"):
    # 放置在侧边栏最顶部，作为 Logo
    # width 设置为稍微窄一点，看起来更像一个专业的 Logo
    st.sidebar.image("icon.jpg", width=250) 
    st.sidebar.markdown("---") # 加一条分割线
else:
    # 兜底：如果文件不在，不显示图片，避免报错干扰，但提示一下用户
    st.sidebar.warning("⚠️ 装饰用的 icon.jpg 未找到，建议上传至 GitHub 仓库根目录。")

st.sidebar.header("📁 上传月度数据 (M1-M4)")
st.sidebar.markdown("*(例如：M1=11月, M2=12月, M3=1月, M4=2月)*")
m1_file = st.sidebar.file_uploader("上传 M1 数据", type=['csv', 'xlsx'])
m2_file = st.sidebar.file_uploader("上传 M2 数据", type=['csv', 'xlsx'])
m3_file = st.sidebar.file_uploader("上传 M3 数据", type=['csv', 'xlsx'])
m4_file = st.sidebar.file_uploader("上传 M4 数据", type=['csv', 'xlsx'])

# 容错函数
def load_data(file):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    # 统一清洗列名，防止空格
    df.columns = df.columns.str.strip()
    return df

if m1_file and m2_file and m3_file and m4_file:
    # 1. 读取数据并打上月度标签
    months_mapping = {
        '01_Month_1': m1_file, 
        '02_Month_2': m2_file, 
        '03_Month_3': m3_file, 
        '04_Month_4': m4_file
    }
    
    cost_col = '渠道Cost' 
    name_col = '素材名称'
    type_col = '素材类型'
    
    all_records = []
    for month_label, file in months_mapping.items():
        df = load_data(file)
        
        # 兼容性处理：防止原表没有素材类型列
        if type_col not in df.columns:
            df[type_col] = ""
            
        # 容错：如果某些行金额为空，填充为0
        df[cost_col] = df[cost_col].fillna(0)
            
        temp = df[[name_col, cost_col, type_col]].copy()
        temp['Month'] = month_label
        # 过滤掉消耗为 0 的素材
        temp = temp[temp[cost_col] > 0] 
        all_records.append(temp)
        
    df_all = pd.concat(all_records, ignore_index=True)
    
    # ==========================================
    # 数据清洗：素材类型智能判定逻辑
    # ==========================================
    def determine_creative_type(row):
        ctype = str(row[type_col]).strip()
        cname = str(row[name_col])
        
        # 如果素材类型为空
        if pd.isna(row[type_col]) or ctype.lower() == 'nan' or ctype == '':
            # 逻辑1：包含两个素材名前缀判定为“视频+试玩”
            if cname.count('WSP_') >= 2:
                return '视频+试玩'
            # 逻辑2：其他判定为 creative set
            else:
                return 'creative set'
        else:
            return ctype

    df_all[type_col] = df_all.apply(determine_creative_type, axis=1)
    
    # ==========================================
    # 逻辑处理：计算素材的 Cohort (同期群)
    # ==========================================
    cohort_df = df_all.groupby(name_col)['Month'].min().reset_index()
    cohort_df.rename(columns={'Month': 'Cohort'}, inplace=True)
    
    df_all = df_all.merge(cohort_df, on=name_col, how='left')
    
    def clean_name(name):
        return name.replace('01_', '').replace('02_', '').replace('03_', '').replace('04_', '').replace('_', ' ')
        
    df_all['Month_Clean'] = df_all['Month'].apply(clean_name)
    df_all['Cohort_Clean'] = df_all['Cohort'].apply(lambda x: clean_name(x) + " 批次")

    # 获取 M1 的老底池素材名单
    m1_creatives = df_all[df_all['Month'] == '01_Month_1'][name_col].unique()

    # ==========================================
    # 创建双 Tab 视图
    # ==========================================
    tab1, tab2 = st.tabs(["📊 大盘整体健康度", "🗂️ 按素材类型接力评估"])
    
    # 定义获取新素材占比的通用函数
    def get_new_creative_ratio(data_subset, month_label):
        month_data = data_subset[data_subset['Month'] == month_label]
        if month_data.empty: return 0
        total_spend = month_data[cost_col].sum()
        if total_spend == 0: return 0
        # 只要不在 M1 名单里，统统算“新血”
        new_spend = month_data[~month_data[name_col].isin(m1_creatives)][cost_col].sum()
        return (new_spend / total_spend) * 100

    # ==========================================
    # Tab 1: 大盘整体评估
    # ==========================================
    with tab1:
        st.header("1. 大盘健康度诊断：新素材 (非M1素材) 占比趋势")
        
        m2_new_ratio = get_new_creative_ratio(df_all, '02_Month_2')
        m3_new_ratio = get_new_creative_ratio(df_all, '03_Month_3')
        m4_new_ratio = get_new_creative_ratio(df_all, '04_Month_4')
        
        if m4_new_ratio >= m3_new_ratio and m3_new_ratio >= m2_new_ratio and m4_new_ratio > 0:
            st.success(f"🔥 **生态极佳 (逐月增长)**：大盘新素材消耗占比爬坡 (M2: {m2_new_ratio:.1f}% ➔ M3: {m3_new_ratio:.1f}% ➔ M4: {m4_new_ratio:.1f}%)。")
        elif m4_new_ratio >= m3_new_ratio and m4_new_ratio > 0:
            st.success(f"👍 **上新健康 (环比回暖)**：本月 (M4) 新素材占比为 **{m4_new_ratio:.1f}%**，高于上月的 **{m3_new_ratio:.1f}%**。")
        else:
            st.error(f"🚨 **新品断层预警!** 大盘 M4 新素材占比下滑至 **{m4_new_ratio:.1f}%** (低于 M3 的 **{m3_new_ratio:.1f}%**)，正在严重依赖吃老本。请立即补充高潜力新品管线！")

        # 同期群图表
        cohort_spend = df_all.groupby(['Month_Clean', 'Cohort_Clean'])[cost_col].sum().reset_index()
        # 强制排序，确保图表堆叠顺序 M1->M2->M3->M4
        cohort_spend.sort_values(by=['Month_Clean', 'Cohort_Clean'], inplace=True)
        
        monthly_totals = cohort_spend.groupby('Month_Clean')[cost_col].transform('sum')
        cohort_spend['Spend Ratio (%)'] = (cohort_spend[cost_col] / monthly_totals) * 100
        
        fig_trend = px.bar(
            cohort_spend, x='Month_Clean', y='Spend Ratio (%)', color='Cohort_Clean',
            # 占比太小的不再柱子上显示文字，防止重叠
            text=cohort_spend['Spend Ratio (%)'].apply(lambda x: f'{x:.1f}%' if x > 2 else ''),
            title="M1-M4 预算流向：不同上线批次(Cohort)的占比演变",
            color_discrete_sequence=px.colors.qualitative.Pastel 
        )
        fig_trend.update_layout(
            barmode='stack', 
            yaxis=dict(range=[0, 100]), 
            hovermode="x unified",
            xaxis_title="消耗发生的月份",
            yaxis_title="消耗金额占比 (%)",
            legend_title="素材首次产生消耗批次"
        )
        # 文字显示在柱子中间
        fig_trend.update_traces(textposition='inside', textfont=dict(color='white', size=14))
        st.plotly_chart(fig_trend, use_container_width=True)

    # ==========================================
    # Tab 2: 按素材类型的接力评估
    # ==========================================
    with tab2:
        st.header("🗂️ 素材类型接力评估诊断")
        st.markdown("从素材类型维度，查看**视频、试玩、Creative Set 等**各自的新血注入趋势表。")
        
        # 1. 简报热图 (甜甜圈图看M4占比)
        m4_df = df_all[df_all['Month'] == '04_Month_4']
        if not m4_df.empty:
            type_spend_m4 = m4_df.groupby(type_col)[cost_col].sum().reset_index().sort_values(by=cost_col, ascending=False)
            fig_pie = px.pie(type_spend_m4, values=cost_col, names=type_col, title='M4 (当月) 各素材类型消耗绝对值占比图', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
            
        st.divider()
        st.subheader("📊 各类型素材新血注入趋势诊断表 (非M1素材占比)")
        st.markdown("比较不同素材类型过去三个月“纯新测试素材”的跑量占比演变。")
        
        creative_types = df_all[type_col].unique()
        type_health_data = []
        
        for ctype in creative_types:
            type_subset = df_all[df_all[type_col] == ctype]
            
            # 环比数据提取
            m2_ratio = get_new_creative_ratio(type_subset, '02_Month_2')
            m3_ratio = get_new_creative_ratio(type_subset, '03_Month_3')
            m4_ratio = get_new_creative_ratio(type_subset, '04_Month_4')
            
            # 只保留当月（M4）还在花的钱的类型
            m4_spend = type_subset[type_subset['Month'] == '04_Month_4'][cost_col].sum()
            
            if m4_spend > 0:
                # 状态逻辑判定
                if m4_ratio >= m3_ratio and m3_ratio >= m2_ratio and m4_ratio > 0:
                    status = "🔥 完美爬坡"
                elif m4_ratio >= m3_ratio and m4_ratio > 0:
                    status = "✅ 稳步接力"
                elif m4_ratio == 0 and m3_ratio == 0 and m2_ratio == 0:
                    status = "💤 纯吃老本 (0%)"
                else:
                    status = "🚨 衰退/断层"
                    
                type_health_data.append({
                    '素材类型': ctype,
                    'M2 新素材占比 (%)': round(m2_ratio, 1),
                    'M3 新素材占比 (%)': round(m3_ratio, 1),
                    'M4 新素材占比 (%)': round(m4_ratio, 1),
                    '接力状态（非M1素材攀升趋势）': status
                })
                
        if type_health_data:
            df_health = pd.DataFrame(type_health_data).sort_values(by='M4 新素材占比 (%)', ascending=False)
            # 使用更专业且支持 Markdown 的表格显示方式
            st.dataframe(
                df_health.style.format({
                    'M2 新素材占比 (%)': '{:.1f}%',
                    'M3 新素材占比 (%)': '{:.1f}%',
                    'M4 新素材占比 (%)': '{:.1f}%'
                }), 
                use_container_width=True,
                hide_index=True # 隐藏 Pandas 的行索引，报表更干净
            )
            
        st.divider()
        
        # 2. 交互式下钻 Cohort 图
        selected_type = st.selectbox("🔍 选择素材类型下钻查看详细 Cohort 衰减图:", df_health['素材类型'].tolist() if type_health_data else creative_types)
        
        if selected_type:
            type_df = df_all[df_all[type_col] == selected_type]
            type_cohort_spend = type_df.groupby(['Month_Clean', 'Cohort_Clean'])[cost_col].sum().reset_index()
            # 同样强制排序
            type_cohort_spend.sort_values(by=['Month_Clean', 'Cohort_Clean'], inplace=True)
            
            type_monthly_totals = type_cohort_spend.groupby('Month_Clean')[cost_col].transform('sum')
            type_cohort_spend['Spend Ratio (%)'] = (type_cohort_spend[cost_col] / type_monthly_totals) * 100
            
            fig_type_trend = px.bar(
                type_cohort_spend, x='Month_Clean', y='Spend Ratio (%)', color='Cohort_Clean',
                text=type_cohort_spend['Spend Ratio (%)'].apply(lambda x: f'{x:.1f}%' if x > 2 else ''),
                title=f"[{selected_type}] 管线的 M1-M4 消耗迁徙图",
                color_discrete_sequence=px.colors.qualitative.Set2 
            )
            fig_type_trend.update_layout(
                barmode='stack', 
                yaxis=dict(range=[0, 100]), 
                hovermode="x unified",
                xaxis_title="消耗发生的月份",
                yaxis_title="消耗金额占比 (%)",
                legend_title="素材批次"
            )
            fig_type_trend.update_traces(textposition='inside', textfont=dict(color='white', size=14))
            st.plotly_chart(fig_type_trend, use_container_width=True)

else:
    # 引导界面加入 Icon 提示，保证第一次打开也没出错
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("icon.jpg"):
            st.image("icon.jpg", width=150)
    with col2:
        st.info("👈 请在左侧侧边栏依次上传 Month 1 到 Month 4 的历史素材导表 (支持 CSV 或 Excel)。系统将根据您的数据，自动为您生成大盘与类型维度的 Cohort 健康度报告。")