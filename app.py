import streamlit as st
import awswrangler as wr
import boto3
import plotly.express as px
import pandas as pd

#KENDİ REGION GLUE  VE S3 KOVA İSİMLERİNİ YAZ:
REGION = "eu-north-1"  
GLUE_DB = "kaggle_analytics_db"
S3_OUTPUT = "s3://final-data61/athena_results/" 

boto3.setup_default_session(region_name=REGION)

@st.cache_data(ttl=60)
def get_datasets():
    tables = wr.catalog.tables(database=GLUE_DB)
    if tables.empty:
        return []
    silver_tables = [t.replace("silver_", "") for t in tables["Table"].tolist() if t.startswith("silver_")]
    return silver_tables

datasets = get_datasets()

if not datasets:
    st.warning("Henüz Glue veritabanında tablo bulunamadı. Bölge (REGION) ayarını kontrol et.")
    st.stop()


selected_ds = st.sidebar.selectbox("📂 Analiz Edilecek Veri Setini Seç:", datasets)
if st.sidebar.button("🔄 Verileri Yenile"):
    st.cache_data.clear()

st.subheader(f" `{selected_ds.upper()}` Veri Seti Derin Analizi")


@st.cache_data(ttl=120)
def load_table(table_name):
    try:
        return wr.athena.read_sql_table(
            table=table_name, 
            database=GLUE_DB,
            s3_output=S3_OUTPUT
        )
    except Exception as e:
        return pd.DataFrame()

df_silver = load_table(f"silver_{selected_ds}")
df_stats = load_table(f"gold_{selected_ds}_stats")
df_corr = load_table(f"gold_{selected_ds}_corr")
df_cat = load_table(f"gold_{selected_ds}_cat")


col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Temiz Satır (Silver)", len(df_silver))
col2.metric("Toplam Sütun Sayısı", len(df_silver.columns))
col3.metric("Sayısal Değişken Sayısı", len(df_stats))
total_outliers = int(df_stats["outlier_count"].sum()) if not df_stats.empty else 0
col4.metric("Tespit Edilen Uç Değer (Outlier)", total_outliers)

st.divider()


tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📐 İstatistikler & Outlier", 
    "🔥 Korelasyon & Dağılım", 
    "🏷️ Kategorik Analiz", 
    "🧹 Temizlenmiş Veri (Silver)",
    "💻 Athena SQL Editörü"
])

with tab1:
    st.markdown("### Sayısal Sütunların Derin İstatistikleri (Gold Katmanı)")
    if not df_stats.empty:
        st.dataframe(df_stats, use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            fig_out = px.bar(
                df_stats, x="column_name", y="outlier_count",
                title="Sütun Bazlı Aykırı Değer (IQR Outlier) Sayıları",
                color="outlier_count", color_continuous_scale="Reds"
            )
            st.plotly_chart(fig_out, use_container_width=True)
        with c2:
            selected_num = st.selectbox("Kutu Grafiği (Boxplot) için sütun seç:", df_stats["column_name"].tolist())
            fig_box = px.box(df_silver, y=selected_num, points="all", title=f"{selected_num} Dağılımı ve Uç Değerler")
            st.plotly_chart(fig_box, use_container_width=True)

with tab2:
    st.markdown("### Değişkenler Arası Korelasyon Matrisi")
    if not df_corr.empty:
        corr_matrix = df_corr.set_index("variable")
        fig_corr = px.imshow(
            corr_matrix, text_auto=".2f", aspect="auto",
            color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            title="Pearson Korelasyon Isı Haritası"
        )
        st.plotly_chart(fig_corr, use_container_width=True)

with tab3:
    st.markdown("### Kategorik Sütunların Frekans Dağılımı")
    if not df_cat.empty:
        cat_cols = df_cat["column_name"].unique().tolist()
        sel_cat = st.selectbox("Kategorik Sütun Seç:", cat_cols)
        sub_cat = df_cat[df_cat["column_name"] == sel_cat]
        
        c1, c2 = st.columns(2)
        with c1:
            fig_bar = px.bar(sub_cat, x="category_value", y="record_count", color="percentage", title=f"{sel_cat} Kayıt Sayıları")
            st.plotly_chart(fig_bar, use_container_width=True)
        with c2:
            fig_pie = px.pie(sub_cat, names="category_value", values="record_count", title=f"{sel_cat} Yüzdesel Dağılım")
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Bu veri setinde kategorik sütun bulunamadı.")

with tab4:
    st.markdown("### Silver Katmanı (Temizlenmiş ve Eksikleri Doldurulmuş Veri)")
    st.dataframe(df_silver.head(200), use_container_width=True)

with tab5:
    st.markdown("### 💻 İnteraktif AWS Athena SQL Editörü")
    
    silver_table_name = f"silver_{selected_ds}"
    

    with st.expander(" Tablo ve Sütun Bilgilerini Gör (Kopya Kağıdı)", expanded=False):
        st.write(f"**Sorgulanabilir Tablo Adları:**")
        st.code(
            f"Temiz Ana Tablo : {silver_table_name}\n"
            f"İstatistikler   : gold_{selected_ds}_stats\n"
            f"Korelasyon      : gold_{selected_ds}_corr\n"
            f"Kategorik Özet  : gold_{selected_ds}_cat"
        )
        if not df_silver.empty:
            st.write("**Ana Tablo (`Silver`) Sütun İsimleri:**")
            st.code(", ".join(df_silver.columns.tolist()))


    default_sql = f"SELECT * \nFROM {silver_table_name} \nLIMIT 25;"
    
    sql_query = st.text_area(
        "SQL Sorgunu Buraya Yaz (Presto / Trino SQL destekler):", 
        value=default_sql, 
        height=150
    )
    
    if st.button("▶️ Sorguyu Athena'da Çalıştır", type="primary"):
        with st.spinner("Athena sorguyu S3 Parquet dosyaları üzerinde çalıştırıyor..."):
            try:
               
                df_sql_result = wr.athena.read_sql_query(
                    sql=sql_query,
                    database=GLUE_DB,
                    s3_output=S3_OUTPUT
                )
                
                st.success(f" Sorgu tamamlandı! Toplam **{len(df_sql_result)}** satır döndü.")
                st.dataframe(df_sql_result, use_container_width=True)
                
          
                csv_data = df_sql_result.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Sorgu Sonucunu CSV Olarak İndir",
                    data=csv_data,
                    file_name=f"{selected_ds}_sql_sonuc.csv",
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f" SQL Hatası: {e}")