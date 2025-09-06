# ===================================================================
# ==          MASTER DATA VALIDATOR APPLICATION (app.py)           ==
# ==        (Final Bilingual Version - Assamese & Bengali)         ==
# ===================================================================
import streamlit as st
import pandas as pd
import os
import re
import pdfplumber
import zipfile
import tempfile

# --- Main Logic Functions ---

def process_csv_files(csv_base_folder_path):
    csv_file_pairs = {}
    for root, _, filenames in os.walk(csv_base_folder_path):
        for filename in filenames:
            if filename.endswith('_e_detail.csv'):
                base = filename.replace('_e_detail.csv', ''); csv_file_pairs.setdefault(base, {})['detail'] = os.path.join(root, filename)
            elif filename.endswith('_e_sup.csv'):
                base = filename.replace('_e_sup.csv', ''); csv_file_pairs.setdefault(base, {})['sup'] = os.path.join(root, filename)
    
    csv_results = []
    for base_name, paths in csv_file_pairs.items():
        if 'detail' in paths and 'sup' in paths:
            try:
                csv_results.append({
                    'folder': os.path.basename(os.path.dirname(paths['detail'])), 'base': base_name,
                    'detail_count': len(pd.read_csv(paths['detail'])), 'sup_count': len(pd.read_csv(paths['sup']))
                })
            except Exception: pass
    return pd.DataFrame(csv_results)

def process_pdf_files(pdf_base_folder_path):
    # ==================== UPGRADED BILINGUAL PDF EXTRACTION FUNCTION ====================
    def extract_data_from_pdf(pdf_path):
        # Define keywords for BOTH languages
        # Original Assamese-like script
        ASSAMESE_MAIN_LIST = '³èº ³èº t¡à[ºA¡à'
        ASSAMESE_ADDITION_HEADER = 'ë™àK'
        ASSAMESE_SUB_DELETION = '¤àƒ'
        ASSAMESE_DELETION_HEADER = 'J) Ç¡‹¹oã¹'
        ASSAMESE_TOTAL_LINE = '³åk¡'
        
        # New Bengali Script
        BENGALI_MAIN_LIST = 'মোট ভোটার'
        BENGALI_ADDITION_HEADER = 'যোগ'
        BENGALI_SUB_DELETION = 'বাদ'
        BENGALI_DELETION_HEADER = 'J)' # Often the letter prefix is enough
        BENGALI_TOTAL_LINE = 'মোট'

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if not pdf.pages:
                    return {'main': 'Empty PDF', 'add': 0, 'sub_del': 0, 'del': 0}

                pages_to_check = pdf.pages[-3:]
                pages_to_check.reverse()

                for page in pages_to_check:
                    text = page.extract_text(x_tolerance=2, y_tolerance=2)
                    
                    # Check for either the Assamese OR Bengali main keyword
                    if text and (ASSAMESE_MAIN_LIST in text or BENGALI_MAIN_LIST in text):
                        main, add, sub_del, dele = "Not Found", 0, 0, 0
                        in_add, in_del, in_sub_del = False, False, False
                        
                        for line in text.split('\n'):
                            # Check for either keyword for each section
                            if ASSAMESE_MAIN_LIST in line or BENGALI_MAIN_LIST in line:
                                nums = re.findall(r'\d+', line)
                                if len(nums) >= 3: main = int(nums[-1])
                            
                            elif ASSAMESE_ADDITION_HEADER in line or BENGALI_ADDITION_HEADER in line:
                                in_add, in_del = True, False
                            
                            elif ASSAMESE_DELETION_HEADER in line or line.strip().startswith(BENGALI_DELETION_HEADER):
                                in_del, in_add = True, False
                            
                            if in_add:
                                if ASSAMESE_SUB_DELETION in line or BENGALI_SUB_DELETION in line:
                                    in_sub_del = True
                                elif in_sub_del and (ASSAMESE_TOTAL_LINE in line or BENGALI_TOTAL_LINE in line):
                                    nums = re.findall(r'\d+', line)
                                    if nums: sub_del = int(nums[-1]); in_sub_del = False
                                # Check for the specific addition line in either script
                                elif 'Î}ì™à\>ã' in line or (len(re.findall(r'\d+', line)) >= 3 and add == 0):
                                    nums = re.findall(r'\d+', line)
                                    if len(nums) >= 3:
                                        add = int(nums[-1])
                                        in_add = False
                            
                            if in_del and (ASSAMESE_TOTAL_LINE in line or BENGALI_TOTAL_LINE in line):
                                nums = re.findall(r'\d+', line)
                                if nums: dele = int(nums[-1]); in_del = False
                        
                        return {'main': main, 'add': add, 'sub_del': sub_del, 'del': dele}

                return {'main': 'Summary Not Found', 'add': 0, 'sub_del': 0, 'del': 0}

        except Exception as e:
            st.warning(f"Warning: Could not process '{os.path.basename(pdf_path)}'. Error: {e}", icon="⚠️")
            return {'main': 'Error', 'add': 0, 'sub_del': 0, 'del': 0}
    # ===================================================================================

    all_pdf_files = [os.path.join(r, f) for r, _, fs in os.walk(pdf_base_folder_path) 
                     for f in fs if f.lower().endswith('.pdf') and not f.startswith('._')]
    all_pdf_files.sort()
    
    pdf_results = []
    progress_bar = st.progress(0, text="Starting PDF processing...")
    total_files = len(all_pdf_files)
    if total_files == 0:
        progress_bar.empty(); return pd.DataFrame() 

    for i, pdf_path in enumerate(all_pdf_files):
        data = extract_data_from_pdf(pdf_path)
        pdf_results.append({
            'Folder': os.path.basename(os.path.dirname(pdf_path)), 'File Name': os.path.basename(pdf_path),
            'Main Total': data['main'], 'Addition Total': data['add'],
            'Sub-Deletion Total': data['sub_del'], 'Deletion Total': data['del']
        })
        progress_bar.progress((i + 1) / total_files, text=f"Processing PDF {i + 1} of {total_files}")
    progress_bar.empty()
    
    df_pdf_report = pd.DataFrame(pdf_results)
    cols_to_sum = ['Addition Total', 'Sub-Deletion Total', 'Deletion Total']
    for col in cols_to_sum:
        df_pdf_report[col] = pd.to_numeric(df_pdf_report[col], errors='coerce').fillna(0).astype(int)
    df_pdf_report['Total Modifications'] = df_pdf_report[cols_to_sum].sum(axis=1)
    return df_pdf_report

# --- STREAMLIT USER INTERFACE ---
st.set_page_config(layout="wide")
st.title('📊 Data Validation and Audit Application')

with st.sidebar:
    st.header('1. Upload Your Data')
    st.info("Please zip your CSV and PDF parent folders before uploading.")
    uploaded_csv_zip = st.file_uploader("Upload CSV Data (.zip)", type="zip")
    uploaded_pdf_zip = st.file_uploader("Upload PDF Data (.zip)", type="zip")

st.header('2. Run the Validation Process')

if st.button('🚀 Start Validation', type="primary", disabled=(not uploaded_csv_zip or not uploaded_pdf_zip)):
    
    with tempfile.TemporaryDirectory() as temp_dir:
        csv_extract_path = os.path.join(temp_dir, "csv_data")
        pdf_extract_path = os.path.join(temp_dir, "pdf_data")
        
        with st.spinner('Extracting zip files...'):
            with zipfile.ZipFile(uploaded_csv_zip, 'r') as zip_ref: zip_ref.extractall(csv_extract_path)
            with zipfile.ZipFile(uploaded_pdf_zip, 'r') as zip_ref: zip_ref.extractall(pdf_extract_path)

        with st.spinner('Phase 1: Processing CSV files...'):
            df_csv = process_csv_files(csv_extract_path)
        
        st.success(f'✅ Phase 1 Complete: Processed {len(df_csv)} CSV pairs.')
        if df_csv.empty:
            st.error("No valid CSV pairs ('_e_detail.csv' and '_e_sup.csv') were found. Aborting."); st.stop()

        st.info('Phase 2: Processing PDF files (this may take a while)...')
        df_pdf = process_pdf_files(pdf_extract_path)
        st.success(f'✅ Phase 2 Complete: Processed {len(df_pdf)} PDF files.')
        if df_pdf.empty:
            st.error("No valid PDF files were found. Aborting."); st.stop()
        
        with st.spinner('Phase 3: Merging data...'):
            df_csv['Merge Key'] = df_csv['base']
            def create_pdf_key(filename):
                match = re.search(r'(A\d+)', str(filename)); return match.group(1) if match else None
            df_pdf['Merge Key'] = df_pdf['File Name'].apply(create_pdf_key)
            df_master = pd.merge(df_csv, df_pdf, on='Merge Key', how='outer')
        st.success('✅ Phase 3 Complete: Data merged.')
        
        with st.spinner('Phase 4: Auditing data for mismatches...'):
            def get_validation_status(row):
                errors = []
                if pd.to_numeric(row.get('detail_count'), errors='coerce') != pd.to_numeric(row.get('Main Total'), errors='coerce'):
                    errors.append(f"Detail Mismatch (CSV: {row.get('detail_count')}, PDF: {row.get('Main Total')})")
                if pd.to_numeric(row.get('sup_count'), errors='coerce') != pd.to_numeric(row.get('Total Modifications'), errors='coerce'):
                    errors.append(f"Sup Mismatch (CSV: {row.get('sup_count')}, PDF: {row.get('Total Modifications')})")
                return "OK" if not errors else " | ".join(errors)
            df_master['Validation Status'] = df_master.apply(get_validation_status, axis=1)
        st.success('✅ Phase 4 Complete: Validation finished.')
        
        st.header('3. Validation Results')
        mismatched_rows = df_master[df_master['Validation Status'] != 'OK']
        
        if mismatched_rows.empty:
            st.balloons(); st.success('🎉 CONGRATULATIONS! All checks passed.')
        else:
            st.error(f"🚨 ATTENTION: Found inconsistencies in {len(mismatched_rows)} rows.")
            st.dataframe(mismatched_rows)
            
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_master.to_excel(writer, index=False, sheet_name='ValidationReport')
        excel_data = output.getvalue()
        
        st.download_button(
            label="📥 Download Final Audited Report (Excel)",
            data=excel_data,
            file_name="FINAL_AUDITED_REPORT.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Please upload both a CSV zip file and a PDF zip file to begin.")
