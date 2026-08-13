import pandas as pd
from pathlib import Path
from datetime import datetime

results_folder = Path("results")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

merged_csv_file = results_folder / f"merged_results_{timestamp}.csv"
merged_excel_file = results_folder / f"merged_results_{timestamp}.xlsx"

desired_columns = [
    "question",
    "fk_grade",
    "smog_grade",
    "fog_grade",
    "flesch_ease",
    "prompt",
    "scoring_text",
    "PEMAT",
    "combo",
    "run_id",
    "timestamp",
    "attempt",
    "source",
    "lineage",
    "structure",
    "avg_sentence_words",
    "sentences_over_12",
    "jargon_count",
    "long_word_count",
    "poly_rate",
    "word_count",
    "objective_score",
    "error",
    "output",
]

csv_files = [
    file for file in results_folder.glob("*.csv")
    if not file.name.startswith("merged_results_")
]

if not csv_files:
    raise FileNotFoundError("No CSV files found in the results folder.")

df_list = []

for file in csv_files:
    df = pd.read_csv(file)
    df["source_file"] = file.name
    df_list.append(df)

merged_df = pd.concat(df_list, ignore_index=True)

existing_desired_columns = [col for col in desired_columns if col in merged_df.columns]
remaining_columns = [col for col in merged_df.columns if col not in existing_desired_columns]

merged_df = merged_df[existing_desired_columns + remaining_columns]

merged_df.to_csv(merged_csv_file, index=False)

merged_df.to_excel(merged_excel_file, index=False)

print(f"Merged {len(csv_files)} CSV files.")
print(f"Saved CSV to: {merged_csv_file}")
print(f"Saved Excel to: {merged_excel_file}")
print(f"Total rows: {len(merged_df)}")
print(f"Total columns: {len(merged_df.columns)}")
