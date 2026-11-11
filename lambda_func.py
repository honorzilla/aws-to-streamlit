import urllib.parse
import awswrangler as wr
import pandas as pd
import numpy as np

# BURAYA KENDİ PROCESSED VE FINAL KOVA İSİMLERİNİ YAZ:
PROCESSED_BUCKET = "senin-processed-bucket-adin"
FINAL_BUCKET = "senin-final-bucket-adin"
GLUE_DATABASE = "kaggle_analytics_db"

def clean_col_name(col):
    tr_map = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU_")
    cleaned = str(col).strip().translate(tr_map).lower()
    return "".join(c if c.isalnum() or c == "_" else "_" for c in cleaned).strip("_")

def lambda_handler(event, context):
    # 1. Tetiklenen CSV dosyasını yakala
    raw_bucket = event['Records'][0]['s3']['bucket']['name']
    raw_key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'])
    dataset_name = clean_col_name(raw_key.split('/')[-1].replace('.csv', ''))
    
    raw_path = f"s3://{raw_bucket}/{raw_key}"
    print(f"Isleniyor: {raw_path} -> Dataset: {dataset_name}")
    
    # 2. Raw CSV'yi oku
    df = wr.s3.read_csv(path=raw_path)
    
    # 3. SILVER (PROCESSED) KATMANI: Temizlik ve Standartlaştırma
    df.columns = [clean_col_name(c) for c in df.columns]
    df = df.dropna(how='all').drop_duplicates()
    
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    for col in num_cols:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())
    for col in cat_cols:
        if df[col].isnull().any():
            df[col] = df[col].fillna("Unknown")
            
    # Processed Bucket'a Parquet olarak yaz ve Glue'ya kaydet
    wr.s3.to_parquet(
        df=df,
        path=f"s3://{PROCESSED_BUCKET}/{dataset_name}/",
        dataset=True,
        mode="overwrite",
        database=GLUE_DATABASE,
        table=f"silver_{dataset_name}"
    )
    
    # 4. GOLD (FINAL) KATMANI: Derin Analiz Tabloları
    
    # A) Sayısal İstatistikler + Çarpıklık (Skew) + Basıklık (Kurtosis) + IQR Aykırı Değer Sayısı
    if num_cols:
        stats_df = df[num_cols].describe().T.reset_index().rename(columns={
            'index': 'column_name', '25%': 'q25', '50%': 'median', '75%': 'q75'
        })
        stats_df['skewness'] = df[num_cols].skew().values
        stats_df['kurtosis'] = df[num_cols].kurtosis().values
        stats_df['iqr'] = stats_df['q75'] - stats_df['q25']
        
        outlier_counts = []
        for col in num_cols:
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            outliers = ((df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))).sum()
            outlier_counts.append(int(outliers))
        stats_df['outlier_count'] = outlier_counts
        
        wr.s3.to_parquet(
            df=stats_df,
            path=f"s3://{FINAL_BUCKET}/{dataset_name}/summary_stats/",
            dataset=True,
            mode="overwrite",
            database=GLUE_DATABASE,
            table=f"gold_{dataset_name}_stats"
        )
        
        # B) Korelasyon Matrisi
        if len(num_cols) > 1:
            corr_df = df[num_cols].corr().reset_index().rename(columns={'index': 'variable'})
            wr.s3.to_parquet(
                df=corr_df,
                path=f"s3://{FINAL_BUCKET}/{dataset_name}/correlations/",
                dataset=True,
                mode="overwrite",
                database=GLUE_DATABASE,
                table=f"gold_{dataset_name}_corr"
            )

    # C) Kategorik Dağılım Analizi (Her kategorik sütun için en sık geçen ilk 20 değer)
    if cat_cols:
        cat_records = []
        for col in cat_cols:
            vc = df[col].astype(str).value_counts().head(20)
            for val, count in vc.items():
                cat_records.append({
                    'column_name': col,
                    'category_value': val,
                    'record_count': int(count),
                    'percentage': round((count / len(df)) * 100, 2)
                })
        if cat_records:
            cat_df = pd.DataFrame(cat_records)
            wr.s3.to_parquet(
                df=cat_df,
                path=f"s3://{FINAL_BUCKET}/{dataset_name}/categorical_dist/",
                dataset=True,
                mode="overwrite",
                database=GLUE_DATABASE,
                table=f"gold_{dataset_name}_cat"
            )

    return {"status": "Success", "dataset": dataset_name, "rows": len(df)}