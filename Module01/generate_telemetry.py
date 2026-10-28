import csv
import random
from datetime import datetime, timedelta

def generate_telemetry():
    random.seed(42)  # Fixed seed for reproducible data
    start_time = datetime(2026, 10, 1, 8, 0, 0)
    machines = ["cnc-01", "cnc-02", "cnc-03"]
    
    with open("Module01/telemetry.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ts", "machine", "temp_c", "vib_rms", "spindle_load"])
        
        current = start_time
        for i in range(1000):
            for m in machines:
                # cnc-02 develops higher vibration over time
                vib_bias = (i / 1000.0) * 1.5 if m == "cnc-02" else 0.0
                writer.writerow([
                    current.isoformat(),
                    m,
                    round(random.uniform(35.0, 65.0), 2),
                    round(random.uniform(0.5, 2.0) + vib_bias, 3),
                    round(random.uniform(20.0, 85.0), 1)
                ])
            current += timedelta(seconds=10)

if __name__ == "__main__":
    generate_telemetry()
    print("Generated Module01/telemetry.csv successfully!")