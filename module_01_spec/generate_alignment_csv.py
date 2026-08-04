import csv
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path("module_01_spec/src").resolve()))
from api import run_module_01_pipeline

def generate_csv():
    corpus_dir = Path("flow-bench/data/output")
    bpmn_files = list(corpus_dir.glob("*.bpmn"))
    csv_file_path = Path("alignment_results.csv")
    excel_file_path = Path("alignment_results.xlsx")
    
    # Define CSV headers
    headers = [
        "corpus",
        "uid", 
        "Phase_3_Status",
        "Mutants_Generated",
        "Killed_by_Property",
        "Killed_by_Disconnection",
        "Phase_4_Status",
        "LTLf_Permits_But_Graph_Doesnt_Count (Loose Rules)",
        "Graph_Permits_But_LTLf_Forbids_Count (Strict Rules)",
        "Traces_Agreed",
        "Converged",
        "Perfectly_Aligned"
    ]
    
    rows = []
    text_rows = []
    
    print(f"Processing {len(bpmn_files)} files. This may take a few minutes...")
    
    for bpmn_file in bpmn_files:
        diagram_id = bpmn_file.name
        print(f"Evaluating {diagram_id}...")
        
        # e.g. uid_100_output.bpmn -> uid="uid_100", corpus="output"
        parts = diagram_id.split("_")
        uid = f"{parts[0]}_{parts[1]}"
        corpus = "output"
        
        with open(bpmn_file, "r", encoding="utf-8") as f:
            xml_content = f.read()
            
        row = {
            "corpus": corpus,
            "uid": uid,
            "Phase_3_Status": "FAIL",
            "Mutants_Generated": 0,
            "Killed_by_Property": 0,
            "Killed_by_Disconnection": 0,
            "Phase_4_Status": "FAIL",
            "LTLf_Permits_But_Graph_Doesnt_Count (Loose Rules)": 0,
            "Graph_Permits_But_LTLf_Forbids_Count (Strict Rules)": 0,
            "Traces_Agreed": 0,
            "Converged": False,
            "Perfectly_Aligned": False
        }
        
        text_row = {
            "corpus": corpus,
            "uid": uid,
            "Gaps_Explanation": "",
            "SCSL_Corrections": "",
            "Auto_Relaxed_Rules": ""
        }
        
        try:
            result = run_module_01_pipeline(xml_content, seed=42)
            
            # Phase 3 Extration
            if result.get("phase_3") and result["phase_3"].get("phase_3_certificate"):
                cert3 = result["phase_3"]["phase_3_certificate"]
                row["Phase_3_Status"] = cert3.get("status", "FAIL")
                row["Mutants_Generated"] = cert3.get("mutants_generated", 0)
                row["Killed_by_Property"] = cert3.get("mutants_killed_by_property", 0)
                row["Killed_by_Disconnection"] = cert3.get("mutants_killed_by_disconnection", 0)
            
            # Phase 4 Extraction
            if result.get("phase_4") and result["phase_4"].get("phase_4_certificate"):
                cert4 = result["phase_4"]["phase_4_certificate"]
                
                if cert4.get("status") == "FAIL_WITH_ERRORS":
                    row["Phase_4_Status"] = "FAIL_WITH_ERRORS"
                else:
                    row["Phase_4_Status"] = "SUCCESS"
                    diff = cert4.get("differential_analysis", {})
                    
                    spec_only = diff.get("traces_spec_only", 0)
                    model_only = diff.get("traces_model_only", 0)
                    
                    row["LTLf_Permits_But_Graph_Doesnt_Count (Loose Rules)"] = spec_only
                    row["Graph_Permits_But_LTLf_Forbids_Count (Strict Rules)"] = model_only
                    row["Traces_Agreed"] = diff.get("traces_agreed", 0)
                    row["Converged"] = cert4.get("convergence", {}).get("converged", False)
                    row["Perfectly_Aligned"] = (model_only == 0)
                    
                    text_row["Gaps_Explanation"] = json.dumps(diff.get("semantic_gaps", []), indent=2)
                    text_row["SCSL_Corrections"] = json.dumps(cert4.get("scsl_corrections", []), indent=2)
                    text_row["Auto_Relaxed_Rules"] = json.dumps(cert4.get("auto_relaxed_rules", []), indent=2)
                    
        except Exception as e:
            row["Phase_4_Status"] = f"ERROR: {str(e)}"
            
        rows.append(row)
        text_rows.append(text_row)
        
    # Write Data View CSV
    data_out_path = Path("eval/results/alignment_results_data_view.csv")
    data_out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(data_out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Done! Results saved to {data_out_path}")
    
    # Write Text View CSV
    text_headers = ["corpus", "uid", "Gaps_Explanation", "SCSL_Corrections", "Auto_Relaxed_Rules"]
    text_out_path = Path("eval/results/alignment_results_text_view.csv")
    with open(text_out_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=text_headers)
        writer.writeheader()
        writer.writerows(text_rows)
        
    print(f"Done! Text view results saved to {text_out_path}")

if __name__ == "__main__":
    generate_csv()
