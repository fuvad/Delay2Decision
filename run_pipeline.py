import subprocess
import sys
import time

# ─────────────────────────────────────────────────────────────────────────────
# EXACT ORDER OF PIPELINE EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
PIPELINE_STAGES = [
    # 1. Clean Data (RAW -> SILVER -> SIMULATION -> VALIDATED)
    "src/pipelines/bronze.py",
    "src/pipelines/silver.py",
    "src/pipelines/jfk_simulation.py",
    "src/ingestion/load_silver_data.py",

    # 2. Base Feature Engineering (SILVER -> GOLD DATAFRAMES)
    "src/pipelines/delay_features.py",         # Computes rolling delays
    "src/pipelines/congestion_features.py",    # Computes terminal congestion

    # 3. Merging & Train/Test Splitting (GOLD -> TRAINING SETS)
    "src/features/feature_engineering.py",            # Splits delay data
    "src/pipelines/buffer_features.py",               # Merges delay+congestion into buffer outputs

    # 4. Machine Learning Model Training (TRAINING SETS -> .PKL MODELS)
    "src/training/train_delay_model.py",
    "src/training/train_congestion_forecaster.py",
    "src/training/train_anomaly_detector.py",
    "src/training/train_buffer_model.py"
]

def run_script(script_path: str):
    """Executes a single python script securely via subprocess."""
    print(f"\n{'='*80}")
    print(f"RUNNING STAGE: {script_path}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    # Run the script exactly as if you typed it in the terminal
    result = subprocess.run([sys.executable, script_path])
    
    elapsed = time.time() - start_time
    
    if result.returncode != 0:
        print(f"\nERROR: Pipeline failed at {script_path} (Exit Code: {result.returncode})")
        print("Please fix the error above before continuing.")
        sys.exit(1)
        
    print(f"\nSUCCESS: {script_path} completed in {elapsed:.1f} seconds.\n")

def main():
    print("""
    ====================================================================
                        DELAY2DECISION ML PIPELINE
    ====================================================================
    This script automates the entire machine learning lifecycle.
    It cleans raw data, computes mathematical features, splits datasets,
    and trains every predictive model sequentially.
    """)
    
    start_time = time.time()
    
    for script in PIPELINE_STAGES:
        run_script(script)
        
    total_time = time.time() - start_time
    print(f"\nPIPELINE COMPLETE! All models successfully retrained in {total_time:.1f} seconds.")
    print("You are now ready to run 'docker-compose build'!")

if __name__ == "__main__":
    main()
