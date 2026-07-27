import pymysql

def copy_database():
    print("Copying database tables and data from sastrybalm_db to safar_db...")
    conn = pymysql.connect(host='127.0.0.1', port=8889, user='root', password='root')
    cur = conn.cursor()
    
    cur.execute("SHOW TABLES FROM sastrybalm_db;")
    tables = [row[0] for row in cur.fetchall()]
    
    cur.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    for table in tables:
        print(f"Copying table {table}...")
        cur.execute(f"DROP TABLE IF EXISTS safar_db.`{table}`;")
        cur.execute(f"CREATE TABLE safar_db.`{table}` LIKE sastrybalm_db.`{table}`;")
        cur.execute(f"INSERT INTO safar_db.`{table}` SELECT * FROM sastrybalm_db.`{table}`;")
        
    cur.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    conn.close()
    print("🎉 Database safar_db created and fully populated!")

if __name__ == "__main__":
    copy_database()
