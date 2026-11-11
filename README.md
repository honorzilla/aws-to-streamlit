# 🚀 Serverless AWS Medallion Data Pipeline & Auto-EDA Dashboard

![AWS](https://img.shields.io/badge/AWS-%23FF9900.svg?style=for-the-badge&logo=amazon-aws&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![Athena](https://img.shields.io/badge/AWS%20Athena-Serverless%20SQL-blue?style=for-the-badge)

Bu proje, herhangi bir ham (raw) veri setini buluta yüklendiği anda otomatik olarak temizleyen, derinlemesine istatistiksel analizlerini (Auto-EDA) çıkaran ve sonuçları interaktif bir web panelinde (Streamlit) görselleştiren **uçtan uca, sunucusuz (serverless) ve olay güdümlü (event-driven) bir veri hattıdır (Data Pipeline).**

Sistem, veri mühendisliğinde endüstri standardı olan **Medallion Mimarisi (Bronze, Silver, Gold)** üzerine inşa edilmiştir.

## 🏗️ Mimari Şema ve Veri Akışı

```mermaid
graph TD
    A[Ham CSV / Kaggle Verisi] -->|Upload| B[(S3: Raw Bucket / Bronze)]
    B -->|S3 ObjectCreated Event| C{AWS Lambda + AWS Data Wrangler}
    
    C -->|1. Temizlik & Tip Dönüşümü| D[(S3: Processed Bucket / Silver)]
    C -->|2. İstatistik, Korelasyon, Outlier Analizi| E[(S3: Final Bucket / Gold)]
    
    D -->|Parquet Formatı| F[AWS Glue Data Catalog]
    E -->|Parquet Formatı| F
    
    F --> G[AWS Athena / Serverless SQL]
    G --> H[Streamlit İnteraktif Dashboard]