import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import re
from openai import OpenAI

# ----------------- 页面设置 -----------------
st.set_page_config(page_title="UA 爆款素材洞察雷达", page_icon="💰", layout="wide")
st.title("💰 海外游戏买量：全链路素材洞察与 AI 策略系统")

# ----------------- 通用大模型流式调用函数 -----------------
def stream_deepseek(prompt, api_key):
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个敏锐、极其专业的海外游戏买量(UA)总监。你擅长用数据说话，直接给出可落地的买量策略。"},
            {"role": "user", "content": prompt}
        ],
        stream=True
    )
    return (chunk.choices[0].delta.content for chunk in response if chunk.choices[0].delta.content is not None)

# ----------------- 聚合函数 -----------------
def aggregate_cost(df, group_cols):
    agg_df = df.groupby(group_cols)['渠道Cost'].sum().reset_index()
    return agg_df.sort_values('渠道Cost', ascending=False)

def render_tag_table(df, tag_col, title_prefix):
    st.markdown(f"#### 🏷️ {title_prefix} 素材属性打标明细表")
    pivot_df = df.groupby(['素材名称', tag_col])['渠道Cost'].sum().unstack(fill_value=0)
    pivot_df['总消耗'] = pivot_df.sum(axis=1)
    pivot_df['覆盖数量'] = (pivot_df.drop(columns=['总消耗']) > 0).sum(axis=1)
    pivot_df['素材属性'] = pivot_df['覆盖数量'].apply(lambda x: "🌐 通用型 (多地/多渠道)" if x > 1 else "🎯 独占型 (单一特征)")
    display_df = pivot_df.sort_values('总消耗', ascending=False).reset_index()
    format_dict = {col: '${:,.2f}' for col in pivot_df.columns if col not in ['总消耗', '覆盖数量', '素材属性']}
    format_dict['总消耗'] = '${:,.2f}'
    st.dataframe(display_df.style.format(format_dict), height=300)

def render_single_drilldown(df, tag_col, title_prefix):
    st.markdown(f"#### 🔍 查看单一{title_prefix}的主力消耗素材 (含素材类型)")
    available_tags = df[tag_col].unique().tolist()
    selected_tag = st.selectbox(f"选择要查看的{title_prefix}：", available_tags, key=f"select_{title_prefix}")
    sub_df = df[df[tag_col] == selected_tag]
    top_sub = aggregate_cost(sub_df, ['素材名称', '素材类型']).head(15)
    fig_sub = px.bar(top_sub, x='渠道Cost', y='素材名称', color='素材类型', orientation='h', 
                     title=f"{selected_tag} {title_prefix}专属 Top 15 消耗素材", text_auto='.2s')
    fig_sub.update_layout(yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_sub, use_container_width=True)

# ----------------- 左侧边栏：全局配置与基础数据上传 -----------------
st.sidebar.header("🤖 DeepSeek 引擎配置")
global_api_key = st.sidebar.text_input("🔑 输入 API Key (必需):", type="password", help="离开页面后自动销毁")
st.sidebar.divider()

st.sidebar.header("📥 基础洞察数据上传")
st.sidebar.markdown("（用于分地区、分渠道及联动分析）")

st.sidebar.subheader("🌍 地区数据上传")
t1_file = st.sidebar.file_uploader("上传 T1 地区数据", type=['csv', 'xlsx'], key='t1')
t2_file = st.sidebar.file_uploader("上传 T2 地区数据", type=['csv', 'xlsx'], key='t2')
t3_file = st.sidebar.file_uploader("上传 T3 地区数据", type=['csv', 'xlsx'], key='t3')
t4_file = st.sidebar.file_uploader("上传 T4 地区数据", type=['csv', 'xlsx'], key='t4')
t5_file = st.sidebar.file_uploader("上传 T5 地区数据", type=['csv', 'xlsx'], key='t5')

st.sidebar.subheader("🚀 渠道数据上传")
c1_file = st.sidebar.file_uploader("上传 C1 渠道数据", type=['csv', 'xlsx'], key='c1')
c2_file = st.sidebar.file_uploader("上传 C2 渠道数据", type=['csv', 'xlsx'], key='c2')
c3_file = st.sidebar.file_uploader("上传 C3 渠道数据", type=['csv', 'xlsx'], key='c3')
c4_file = st.sidebar.file_uploader("上传 C4 渠道数据", type=['csv', 'xlsx'], key='c4')
c5_file = st.sidebar.file_uploader("上传 C5 渠道数据", type=['csv', 'xlsx'], key='c5')

def process_upload_slots(file_dict, tag_name):
    df_list = []
    for tag_label, file in file_dict.items():
        if file is not None:
            df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
            df[tag_name] = tag_label
            df_list.append(df)
            
    if df_list:
        combined_df = pd.concat(df_list, ignore_index=True).dropna(subset=['素材名称'])
        def fill_creative_type(row):
            c_type = row.get('素材类型', pd.NA)
            c_name = str(row['素材名称'])
            if pd.isna(c_type) or str(c_type).strip() == '':
                if c_name.count('WSP_') >= 2 or len(re.findall(r'_[0-9]{6}_', c_name)) >= 2: return '视频+试玩'
                else: return 'creative set'
            return c_type
        combined_df['素材类型'] = combined_df.apply(fill_creative_type, axis=1)
        return combined_df
    return pd.DataFrame()

df_regions = process_upload_slots({'T1': t1_file, 'T2': t2_file, 'T3': t3_file, 'T4': t4_file, 'T5': t5_file}, 'Region')
df_channels = process_upload_slots({'C1': c1_file, 'C2': c2_file, 'C3': c3_file, 'C4': c4_file, 'C5': c5_file}, 'Channel')

# ----------------- 主界面分析展示 (重组后的 6 个 Tab) -----------------
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "⏳ 1. 接力健康度评估", 
    "🌍 2. 分地区消耗分析", 
    "🚀 3. 分渠道消耗分析", 
    "⚔️ 4. 地区&渠道联动", 
    "⭐ 5. WSP评级", 
    "🎧 6. ASMR评级"
])

# ==================== TAB 1: 接力健康度评估 ====================
with tab1:
    st.markdown("### ⏳ 素材接力与同期群评估 (Cohort)")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: m1_f = st.file_uploader("上传 M1 月度", type=['csv', 'xlsx'], key='m1')
    with col_m2: m2_f = st.file_uploader("上传 M2 月度", type=['csv', 'xlsx'], key='m2')
    with col_m3: m3_f = st.file_uploader("上传 M3 月度", type=['csv', 'xlsx'], key='m3')
    with col_m4: m4_f = st.file_uploader("上传 M4 月度", type=['csv', 'xlsx'], key='m4')

    if m1_f and m2_f and m3_f and m4_f:
        df_list_m = []
        for label, f in zip(['01_M1', '02_M2', '03_M3', '04_M4'], [m1_f, m2_f, m3_f, m4_f]):
            df_m = pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f)
            df_m['Month'] = label
            if '素材类型' not in df_m.columns: df_m['素材类型'] = ""
            df_m = df_m[df_m['渠道Cost'] > 0]
            df_list_m.append(df_m[['素材名称', '渠道Cost', '素材类型', 'Month']])
            
        df_all = pd.concat(df_list_m)
        def fill_ctype(row):
            ctype, cname = str(row['素材类型']).strip(), str(row['素材名称'])
            if pd.isna(row['素材类型']) or ctype.lower() == 'nan' or ctype == '':
                if cname.count('WSP_') >= 2 or len(re.findall(r'_[0-9]{6}_', cname)) >= 2: return '视频+试玩'
                return 'creative set'
            return ctype
        df_all['素材类型'] = df_all.apply(fill_ctype, axis=1)
        
        cohort_df = df_all.groupby('素材名称')['Month'].min().reset_index()
        cohort_df.rename(columns={'Month': 'Cohort'}, inplace=True)
        df_all = df_all.merge(cohort_df, on='素材名称', how='left')
        
        def clean_name(name): return name.replace('01_', '').replace('02_', '').replace('03_', '').replace('04_', '').replace('_', ' ')
        df_all['Month_Clean'] = df_all['Month'].apply(clean_name)
        df_all['Cohort_Clean'] = df_all['Cohort'].apply(lambda x: clean_name(x) + " 批次")
        m1_creatives = df_all[df_all['Month'] == '01_M1']['素材名称'].unique()
        
        def get_new_ratio(data, m_label):
            m_data = data[data['Month'] == m_label]
            if m_data.empty or m_data['渠道Cost'].sum() == 0: return 0
            return (m_data[~m_data['素材名称'].isin(m1_creatives)]['渠道Cost'].sum() / m_data['渠道Cost'].sum()) * 100

        st.divider()
        st.subheader("📊 广告素材类型接力健康度汇总")
        health_data = []
        for ctype in df_all['素材类型'].unique():
            sub = df_all[df_all['素材类型'] == ctype]
            if sub['渠道Cost'].sum() > 0:
                health_data.append({
                    '素材类型': ctype,
                    'M2 新素材占比 (%)': round(get_new_ratio(sub, '02_M2'), 1),
                    'M3 新素材占比 (%)': round(get_new_ratio(sub, '03_M3'), 1),
                    'M4 新素材占比 (%)': round(get_new_ratio(sub, '04_M4'), 1)
                })
        
        df_health = pd.DataFrame(health_data).sort_values(by='M4 新素材占比 (%)', ascending=False)
        st.dataframe(df_health.style.format({'M2 新素材占比 (%)': '{:.1f}%', 'M3 新素材占比 (%)': '{:.1f}%', 'M4 新素材占比 (%)': '{:.1f}%'}), use_container_width=True)

        if st.button("🤖 召唤 DeepSeek 诊断接力健康度", key="ai_tab1"):
            if not global_api_key: st.warning("请在左侧边栏配置 API Key")
            else:
                with st.spinner("AI 正在评估生命周期..."):
                    prompt = f"""这是我们各广告类型在 M2、M3、M4 的【新血素材消耗占比(%)】数据：
                    \n{df_health.to_markdown()}
                    \n请分析不同类型素材的生命周期健康度：
                    1. 哪些类型呈现出完美的换血接力（逐月上升）？值得继续投资源？
                    2. 哪些类型出现了严重的断层吃老本现象（降至0或持续走低）？需要立刻补充新素材？
                    直接给出专业的 UA 指导建议，使用清晰的 Markdown 和列表排版。"""
                    st.write_stream(stream_deepseek(prompt, global_api_key))
                    
        # --- 恢复完整的图表区 ---
        st.divider()
        st.subheader("📈 大盘趋势：M1-M4 预算流向与同期群演变")
        cohort_spend = df_all.groupby(['Month_Clean', 'Cohort_Clean'])['渠道Cost'].sum().reset_index()
        monthly_totals = cohort_spend.groupby('Month_Clean')['渠道Cost'].transform('sum')
        cohort_spend['Spend Ratio (%)'] = (cohort_spend['渠道Cost'] / monthly_totals) * 100
        fig_trend = px.bar(
            cohort_spend, x='Month_Clean', y='Spend Ratio (%)', color='Cohort_Clean',
            text=cohort_spend['Spend Ratio (%)'].apply(lambda x: f'{x:.1f}%' if x > 2 else ''),
            title="全局预算流向：不同上线批次的生命周期占比",
            color_discrete_sequence=px.colors.qualitative.Pastel 
        )
        fig_trend.update_layout(barmode='stack', yaxis=dict(range=[0, 100]), hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)
        
        st.markdown("#### 🔍 查看单一素材类型的接力下钻图")
        selected_type = st.selectbox("选择要查阅的广告素材类型:", df_all['素材类型'].unique())
        if selected_type:
            type_df = df_all[df_all['素材类型'] == selected_type]
            type_cohort_spend = type_df.groupby(['Month_Clean', 'Cohort_Clean'])['渠道Cost'].sum().reset_index()
            type_monthly_totals = type_cohort_spend.groupby('Month_Clean')['渠道Cost'].transform('sum')
            type_cohort_spend['Spend Ratio (%)'] = (type_cohort_spend['渠道Cost'] / type_monthly_totals) * 100
            fig_type_trend = px.bar(
                type_cohort_spend, x='Month_Clean', y='Spend Ratio (%)', color='Cohort_Clean',
                text=type_cohort_spend['Spend Ratio (%)'].apply(lambda x: f'{x:.1f}%' if x > 2 else ''),
                title=f"[{selected_type}] 分类下的 M1-M4 消耗迁徙图",
                color_discrete_sequence=px.colors.qualitative.Set2 
            )
            fig_type_trend.update_layout(barmode='stack', yaxis=dict(range=[0, 100]), hovermode="x unified")
            st.plotly_chart(fig_type_trend, use_container_width=True)
    else:
        st.info("👆 请上传全部 M1 - M4 数据以解锁 Cohort 评估及图表。")

# ==================== TAB 2: 分地区消耗分析 ====================
with tab2:
    if not df_regions.empty:
        st.subheader("🌍 不同类型广告素材的【分地区】消耗全景")
        type_reg = df_regions.groupby(['Region', '素材类型'])['渠道Cost'].sum().reset_index()
        fig_tr = px.bar(type_reg, x='Region', y='渠道Cost', color='素材类型', barmode='group', text_auto='.2s', title="各地区的主力素材类型结构")
        st.plotly_chart(fig_tr, use_container_width=True)
        
        st.divider()
        # 恢复被删掉的打标明细表和单区下钻图表
        render_tag_table(df_regions, 'Region', "多地区")
        st.divider()
        render_single_drilldown(df_regions, 'Region', "地区")
        st.divider()
        
        if st.button("🤖 召唤 DeepSeek 发掘地区差异雷达", key="ai_tab2"):
            if not global_api_key: st.warning("请在左侧边栏配置 API Key")
            else:
                with st.spinner("AI 正在拉取地区差异表现..."):
                    top_creatives = df_regions.groupby('素材名称')['渠道Cost'].sum().nlargest(30).index
                    pivot_reg = df_regions[df_regions['素材名称'].isin(top_creatives)].groupby(['素材名称', 'Region'])['渠道Cost'].sum().unstack(fill_value=0)
                    reg_total = df_regions.groupby('Region')['渠道Cost'].sum()
                    pivot_reg_pct = (pivot_reg / reg_total * 100).fillna(0).round(1).astype(str) + '%'
                    reg_combined = pivot_reg.round(0).astype(int).astype(str) + " (" + pivot_reg_pct + ")"
                    
                    prompt = f"""这是大盘 Top 30 素材在各地区的【消耗金额及大盘占比】数据表：\n{reg_combined.to_markdown()}
                    \n请帮我深度排查这批素材在不同地区之间的【消耗差异异常】。
                    重点挑出 3-5 个**在某个地区消耗占比极高（爆款），但在另一个主流地区消耗占比极低（可能未上线/出价断档）**的偏科素材。
                    严格按照以下格式输出卡片：
                    #### 🎬 [素材名称]
                    * **📊 区域落差**：[说明哪个区极高，哪个区为0]
                    * **💡 策略动作**：[提供针对性的排查漏传或调整出价的具体指令]"""
                    st.write_stream(stream_deepseek(prompt, global_api_key))
    else: st.info("👈 请在左侧上传地区数据")

# ==================== TAB 3: 分渠道消耗分析 ====================
with tab3:
    if not df_channels.empty:
        st.subheader("🚀 不同类型广告素材的【分渠道】消耗全景")
        type_chn = df_channels.groupby(['Channel', '素材类型'])['渠道Cost'].sum().reset_index()
        fig_tc = px.bar(type_chn, x='Channel', y='渠道Cost', color='素材类型', barmode='group', text_auto='.2s', title="各渠道的主力素材类型结构")
        st.plotly_chart(fig_tc, use_container_width=True)

        st.divider()
        # 恢复被删掉的打标明细表和单渠道下钻图表
        render_tag_table(df_channels, 'Channel', "多渠道")
        st.divider()
        render_single_drilldown(df_channels, 'Channel', "渠道")
        st.divider()

        if st.button("🤖 召唤 DeepSeek 发掘渠道差异雷达", key="ai_tab3"):
            if not global_api_key: st.warning("请在左侧边栏配置 API Key")
            else:
                with st.spinner("AI 正在拉取渠道差异表现..."):
                    top_creatives = df_channels.groupby('素材名称')['渠道Cost'].sum().nlargest(30).index
                    pivot_chn = df_channels[df_channels['素材名称'].isin(top_creatives)].groupby(['素材名称', 'Channel'])['渠道Cost'].sum().unstack(fill_value=0)
                    chn_total = df_channels.groupby('Channel')['渠道Cost'].sum()
                    pivot_chn_pct = (pivot_chn / chn_total * 100).fillna(0).round(1).astype(str) + '%'
                    chn_combined = pivot_chn.round(0).astype(int).astype(str) + " (" + pivot_chn_pct + ")"
                    
                    prompt = f"""这是大盘 Top 30 素材在各渠道的【消耗金额及大盘占比】数据表：\n{chn_combined.to_markdown()}
                    \n请排查素材在不同渠道的【投放偏差与漏洞】。
                    找出 3-5 个在不同渠道表现极度断层（例如在 C1 是统治级但在 C2 毫无建树）的素材，这极大可能是投手忘记传素材或出价过低。
                    严格按照以下格式输出卡片：
                    #### 🎬 [素材名称]
                    * **📊 渠道落差**：[列举悬殊的对比数据]
                    * **💡 策略动作**：[给出排查漏传、一键克隆或单独冷启动等操作建议]"""
                    st.write_stream(stream_deepseek(prompt, global_api_key))
    else: st.info("👈 请在左侧上传渠道数据")

# ==================== TAB 4: 地区&渠道联动分析 ====================
with tab4:
    if not df_regions.empty and not df_channels.empty:
        common_creatives = set(df_regions['素材名称']).intersection(set(df_channels['素材名称']))
        if common_creatives:
            insight_data = []
            for name in common_creatives:
                r_data = df_regions[df_regions['素材名称'] == name]
                c_data = df_channels[df_channels['素材名称'] == name]
                insight_data.append({
                    '素材名称': name, '素材类型': r_data['素材类型'].iloc[0],
                    '综合体量(Cost)': max(r_data['渠道Cost'].sum(), c_data['渠道Cost'].sum()),
                    '覆盖地区数': r_data['Region'].nunique(), '主力地区': r_data.groupby('Region')['渠道Cost'].sum().idxmax(),
                    '覆盖渠道数': c_data['Channel'].nunique(), '主力渠道': c_data.groupby('Channel')['渠道Cost'].sum().idxmax()
                })
            insight_df = pd.DataFrame(insight_data)
            insight_df['jx'] = insight_df['覆盖地区数'] + np.random.uniform(-0.15, 0.15, size=len(insight_df))
            insight_df['jy'] = insight_df['覆盖渠道数'] + np.random.uniform(-0.15, 0.15, size=len(insight_df))
            
            st.markdown("#### 🎯 素材多极化覆盖象限矩阵")
            fig_matrix = px.scatter(insight_df, x='jx', y='jy', size='综合体量(Cost)', color='素材类型', hover_name='素材名称', labels={'jx': '覆盖地区数', 'jy': '覆盖渠道数'})
            st.plotly_chart(fig_matrix, use_container_width=True)
            
            st.markdown("#### 🏆 跨维主力素材画像全景表")
            st.dataframe(insight_df.sort_values('综合体量(Cost)', ascending=False).drop(columns=['jx', 'jy']).style.format({'综合体量(Cost)': '${:,.2f}'}), height=300)
            
            st.divider()
            # 恢复被删掉的 360° 单素材比对饼图
            st.markdown("#### 🔍 单一素材 360° 画像下钻")
            sorted_commons = insight_df.sort_values('综合体量(Cost)', ascending=False)['素材名称'].tolist()
            selected_creative = st.selectbox("选择要深挖分布结构的特定素材：", sorted_commons)
            if selected_creative:
                col1, col2 = st.columns(2)
                with col1:
                    c_reg = df_regions[df_regions['素材名称'] == selected_creative]
                    st.plotly_chart(px.pie(aggregate_cost(c_reg, ['Region']), values='渠道Cost', names='Region', title=f"🌎 花费【地区】分布", hole=0.4), use_container_width=True)
                with col2:
                    c_chn = df_channels[df_channels['素材名称'] == selected_creative]
                    st.plotly_chart(px.pie(aggregate_cost(c_chn, ['Channel']), values='渠道Cost', names='Channel', title=f"🚀 花费【渠道】分布", hole=0.4), use_container_width=True)
        else: st.warning("您上传的地区表和渠道表之间，没有发现同名的素材。")
    else: st.info("👈 请上传地区和渠道数据解锁跨维联动。")

# ================== 通用数据准备函数 (评级模块) ==================
def read_rating_files(files):
    df_list = [pd.read_csv(f) if f.name.endswith('.csv') else pd.read_excel(f) for f in files]
    return pd.concat(df_list, ignore_index=True).dropna(subset=['素材名称']) if df_list else pd.DataFrame()

def style_rating_df(df):
    return df.style.format({'消耗(Cost)': '${:,.2f}', '7日ROAS': '{:.2%}', '1日留存': '{:.2%}'}).applymap(
        lambda x: 'background-color: #d4edda; font-weight: bold' if '优秀' in str(x) else 
                  ('background-color: #fff3cd; font-weight: bold' if '潜力' in str(x) else 
                  ('background-color: #cce5ff; font-weight: bold' if '通过' in str(x) else '')), subset=['评级结果'])

def generate_funnel_ui(df_res, title_prefix):
    if df_res.empty: return
    st.subheader(title_prefix)
    c1, c2, c3, c4 = st.columns(4)
    tot = len(df_res)
    exc = len(df_res[df_res['评级结果'].str.contains('优秀')])
    pot = len(df_res[df_res['评级结果'].str.contains('优秀|潜力')])
    pas = len(df_res[df_res['评级结果'].str.contains('优秀|潜力|通过')])
    c1.metric("判定素材数", f"{tot} 个")
    c2.metric("🌟 优秀素材", f"{exc}个 ({exc/tot*100:.1f}%)" if tot else "0个")
    c3.metric("🔥 潜力及以上", f"{pot}个 ({pot/tot*100:.1f}%)" if tot else "0个")
    c4.metric("✅ 通过及以上", f"{pas}个 ({pas/tot*100:.1f}%)" if tot else "0个")
    st.dataframe(style_rating_df(df_res), use_container_width=True, height=250)

# ==================== TAB 5: WSP 评级 ====================
with tab5:
    st.markdown("### 📥 上传 WSP 评级专属数据源 (区分 iOS / Android)")
    col_w_i, col_w_a = st.columns(2)
    with col_w_i:
        ios_g_f = st.file_uploader("1️⃣ iOS【谷歌渠道】", type=['csv', 'xlsx'], accept_multiple_files=True, key='wg1')
        ios_ng_f = st.file_uploader("2️⃣ iOS【非谷歌渠道】", type=['csv', 'xlsx'], accept_multiple_files=True, key='wng1')
    with col_w_a:
        aos_g_f = st.file_uploader("3️⃣ Android【谷歌渠道】", type=['csv', 'xlsx'], accept_multiple_files=True, key='wg2')
        aos_ng_f = st.file_uploader("4️⃣ Android【非谷歌渠道】", type=['csv', 'xlsx'], accept_multiple_files=True, key='wng2')

    df_w_i_g = read_rating_files(ios_g_f)
    df_w_i_ng = read_rating_files(ios_ng_f)
    df_w_a_g = read_rating_files(aos_g_f)
    df_w_a_ng = read_rating_files(aos_ng_f)
    
    if any(not d.empty for d in [df_w_i_g, df_w_i_ng, df_w_a_g, df_w_a_ng]):
        def run_wsp_logic(df_g, df_ng, os_name, roas_target, is_pt_zone):
            res = []
            if not df_g.empty:
                df_g_flt = df_g[df_g['素材名称'].str.contains('PT')] if is_pt_zone else df_g[~df_g['素材名称'].str.contains('PT')]
                agg_g = df_g_flt.groupby('素材名称', as_index=False).agg({'渠道Cost': 'sum'})
                for _, r in agg_g.iterrows():
                    c = r['渠道Cost']
                    rating = '🌟 优秀素材' if c > 3000 else ('🔥 潜力素材' if c > 2000 else ('✅ 通过素材' if c > 500 else '❌ 未达标'))
                    res.append({'素材名称': r['素材名称'], '渠道': '谷歌', '评级结果': rating, '消耗(Cost)': c, '7日ROAS': 0, '1日留存': 0})
                    
            if not df_ng.empty:
                df_ng_flt = df_ng[df_ng['素材名称'].str.contains('PT')] if is_pt_zone else df_ng[~df_ng['素材名称'].str.contains('PT')]
                if not df_ng_flt.empty:
                    agg_ng = df_ng_flt.copy()
                    agg_ng['d1_rev'] = agg_ng['渠道Cost'] * agg_ng['1日总ROAS']
                    agg_ng['d7_rev'] = agg_ng['渠道Cost'] * agg_ng['7日总ROAS']
                    agg_ng['d1_ret'] = agg_ng['渠道Installs'] * agg_ng['1日留存率(%)']
                    agg_ng = agg_ng.groupby('素材名称', as_index=False).agg({'渠道Cost':'sum', '渠道Installs':'sum', 'd1_rev':'sum', 'd7_rev':'sum', 'd1_ret':'sum'})
                    agg_ng['7日ROAS'] = agg_ng['d7_rev'] / agg_ng['渠道Cost'].replace(0, 1)
                    agg_ng['1日留存'] = agg_ng['d1_ret'] / agg_ng['渠道Installs'].replace(0, 1)
                    
                    avg_roas = agg_ng['7日ROAS'].mean()
                    exc_thres = avg_roas * 0.9 if is_pt_zone else avg_roas * 0.8
                    
                    for _, r in agg_ng.iterrows():
                        c, roas, ret = r['渠道Cost'], r['7日ROAS'], r['1日留存']
                        rating = '❌ 未达标'
                        if c > 2000 and roas > exc_thres: rating = '🌟 优秀素材'
                        elif ret > 0.22:
                            if c > 500 and roas > roas_target: rating = '🔥 潜力素材'
                            elif c > 100 and roas > roas_target: rating = '✅ 通过素材'
                        res.append({'素材名称': r['素材名称'], '渠道': '非谷歌', '评级结果': rating, '消耗(Cost)': c, '7日ROAS': roas, '1日留存': ret})
            return pd.DataFrame(res)

        wsp_ios_nopt = run_wsp_logic(df_w_i_g, df_w_i_ng, "iOS", 0.35, False)
        wsp_ios_pt = run_wsp_logic(df_w_i_g, df_w_i_ng, "iOS", 0.35, True)
        wsp_aos_nopt = run_wsp_logic(df_w_a_g, df_w_a_ng, "Android", 0.25, False)
        wsp_aos_pt = run_wsp_logic(df_w_a_g, df_w_a_ng, "Android", 0.25, True)
        
        for df in [wsp_ios_nopt, wsp_ios_pt, wsp_aos_nopt, wsp_aos_pt]:
            if not df.empty:
                df['ord'] = df['评级结果'].map({'🌟 优秀素材':1, '🔥 潜力素材':2, '✅ 通过素材':3, '❌ 未达标':4}).fillna(9)
                df.sort_values(['ord', '消耗(Cost)'], ascending=[True, False], inplace=True)
                df.drop(columns=['ord'], inplace=True)

        st.divider()
        generate_funnel_ui(wsp_ios_nopt, "🍎 iOS【非巴西】榜单")
        generate_funnel_ui(wsp_ios_pt, "🍎 iOS【巴西专区 (含PT)】榜单")
        generate_funnel_ui(wsp_aos_nopt, "🤖 Android【非巴西】榜单")
        generate_funnel_ui(wsp_aos_pt, "🤖 Android【巴西专区 (含PT)】榜单")
        
        df_all_wsp = pd.concat([wsp_ios_nopt, wsp_ios_pt, wsp_aos_nopt, wsp_aos_pt])
        if st.button("🤖 AI 洞察 WSP: 寻找差临门一脚的升级潜力股", key="wsp_ai"):
            if not global_api_key: st.warning("请在左侧边栏配置 API Key")
            else:
                with st.spinner("正在呼叫 DeepSeek 分析 WSP 评级突破口..."):
                    prompt = f"""这是本次 WSP 大盘各素材的评级表现：\n{df_all_wsp.to_markdown()}
                    \n作为优化大师，请帮我挖掘具有【评级跃迁机会】的素材名单：
                    1. **冲刺潜力股**：在评为“通过素材”的名单里，找到那些 ROAS 和留存极好，但仅仅因为 Cost 消耗不足而没被评为“潜力”的素材。
                    2. **冲击神坛股**：在评为“潜力素材”的名单里，找到各数据逼近“优秀”水槛（消耗差一点或ROAS差微弱百分比）的素材。
                    请直接列出 3-5 个最具跃升价值的素材名，指出它的优势数据，并给出（例如：大胆放宽受众定向、立刻大幅提价等）动作指令！"""
                    st.write_stream(stream_deepseek(prompt, global_api_key))

# ==================== TAB 6: ASMR 评级 ====================
with tab6:
    st.markdown("### 📥 上传 ASMR 评级专属数据源 (区分 iOS / Android)")
    col_a_i, col_a_a = st.columns(2)
    with col_a_i:
        a_ios_g = st.file_uploader("1️⃣ iOS【谷歌】", type=['csv', 'xlsx'], accept_multiple_files=True, key='ag1')
        a_ios_ng = st.file_uploader("2️⃣ iOS【非谷歌】", type=['csv', 'xlsx'], accept_multiple_files=True, key='ang1')
    with col_a_a:
        a_aos_g = st.file_uploader("3️⃣ Android【谷歌】", type=['csv', 'xlsx'], accept_multiple_files=True, key='ag2')
        a_aos_ng = st.file_uploader("4️⃣ Android【非谷歌】", type=['csv', 'xlsx'], accept_multiple_files=True, key='ang2')

    df_a_i_g = read_rating_files(a_ios_g)
    df_a_i_ng = read_rating_files(a_ios_ng)
    df_a_a_g = read_rating_files(a_aos_g)
    df_a_a_ng = read_rating_files(a_aos_ng)
    
    if any(not d.empty for d in [df_a_i_g, df_a_i_ng, df_a_a_g, df_a_a_ng]):
        def run_asmr_logic(df_g, df_ng, os_name):
            res = []
            if not df_g.empty:
                agg_g = df_g.groupby('素材名称', as_index=False).agg({'渠道Cost': 'sum'})
                for _, r in agg_g.iterrows():
                    c = r['渠道Cost']
                    rating = '🌟 优秀素材' if c > 500 else ('🔥 潜力素材' if c > 200 else ('✅ 测试通过' if c > 50 else '❌ 未达标'))
                    res.append({'素材名称': r['素材名称'], '渠道': '谷歌', '评级结果': rating, '消耗(Cost)': c, '7日ROAS': 0, '1日留存': 0})
                    
            if not df_ng.empty:
                agg_ng = df_ng.copy()
                agg_ng['d1_rev'] = agg_ng['渠道Cost'] * agg_ng['1日总ROAS']
                agg_ng['d7_rev'] = agg_ng['渠道Cost'] * agg_ng['7日总ROAS']
                agg_ng['d1_ret'] = agg_ng['渠道Installs'] * agg_ng['1日留存率(%)']
                agg_ng = agg_ng.groupby('素材名称', as_index=False).agg({'渠道Cost':'sum', '渠道Installs':'sum', 'd1_rev':'sum', 'd7_rev':'sum', 'd1_ret':'sum'})
                agg_ng['7日ROAS'] = agg_ng['d7_rev'] / agg_ng['渠道Cost'].replace(0, 1)
                agg_ng['1日留存'] = agg_ng['d1_ret'] / agg_ng['渠道Installs'].replace(0, 1)
                
                for _, r in agg_ng.iterrows():
                    c, roas, ret = r['渠道Cost'], r['7日ROAS'], r['1日留存']
                    rating = '❌ 未达标'
                    if os_name == 'iOS':
                        if c > 1000 and roas > 0.35: rating = '🌟 优秀素材'
                        elif c > 300 and roas > 0.33 and ret > 0.25: rating = '🔥 潜力素材'
                        elif c > 50 and ret > 0.25: rating = '✅ 测试通过'
                    else:
                        if c > 800 and roas > 0.40: rating = '🌟 优秀素材'
                        elif c > 300 and roas > 0.38 and ret > 0.20: rating = '🔥 潜力素材'
                        elif c > 50 and ret > 0.20: rating = '✅ 测试通过'
                    res.append({'素材名称': r['素材名称'], '渠道': '非谷歌', '评级结果': rating, '消耗(Cost)': c, '7日ROAS': roas, '1日留存': ret})
            return pd.DataFrame(res)

        asmr_ios = run_asmr_logic(df_a_i_g, df_a_i_ng, 'iOS')
        asmr_aos = run_asmr_logic(df_a_a_g, df_a_a_ng, 'Android')
        
        for df in [asmr_ios, asmr_aos]:
            if not df.empty:
                df['ord'] = df['评级结果'].map({'🌟 优秀素材':1, '🔥 潜力素材':2, '✅ 测试通过':3, '❌ 未达标':4}).fillna(9)
                df.sort_values(['ord', '消耗(Cost)'], ascending=[True, False], inplace=True)
                df.drop(columns=['ord'], inplace=True)

        st.divider()
        generate_funnel_ui(asmr_ios, "🍎 ASMR iOS 评级榜单")
        generate_funnel_ui(asmr_aos, "🤖 ASMR Android 评级榜单")
        
        df_all_asmr = pd.concat([asmr_ios, asmr_aos])
        if st.button("🤖 AI 洞察 ASMR: 挖掘跃迁潜力素材", key="asmr_ai"):
            if not global_api_key: st.warning("请在左侧边栏配置 API Key")
            else:
                with st.spinner("正在呼叫 DeepSeek 挖掘 ASMR 隐形金矿..."):
                    prompt = f"""这是 ASMR 大盘各素材评级及详细(消耗、ROAS、留存)数据表：\n{df_all_asmr.to_markdown()}
                    \n作为顶尖优化师，请敏锐地找出可以被“人工干预保送”的潜力黑马：
                    1. 挑出 2-3 个从 **“测试通过”极大概率跃迁至“潜力素材”** 的目标（例如 ROAS 或 留存 极高，但消耗卡在边缘）。
                    2. 挑出 2-3 个从 **“潜力素材”极大概率突破为“优秀爆款”** 的目标。
                    请用 Markdown 排版，指出其目前被卡住的原因（是消耗不够，还是某项比率差一丁点？），并要求 UA 人员对其放开预算或微调素材！"""
                    st.write_stream(stream_deepseek(prompt, global_api_key))