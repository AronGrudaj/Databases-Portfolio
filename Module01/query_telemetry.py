import sqlite3

def get_high_vibration(machine_name, threshold):
    # NEVER string-interpolate user input into SQL query strings!
    # ALWAYS use bound parameters (?) to prevent SQL Injection.
    conn = sqlite3.connect("Module01/telemetry.db")
    cursor = conn.cursor()
    
    query = """
        SELECT ts, machine, temp_c, vib_rms 
        FROM telemetry 
        WHERE machine = ? AND vib_rms > ?
        ORDER BY vib_rms DESC
        LIMIT 5;
    """
    
    cursor.execute(query, (machine_name, threshold))
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    print("Top high-vibration readings for cnc-02:")
    results = get_high_vibration("cnc-02", 2.5)
    for r in results:
        print(r)