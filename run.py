import uvicorn
from db_migrate import run_migrations

if __name__ == "__main__":
    try:
        run_migrations()
    except Exception as e:
        print(f"Pre-startup migration error: {e}")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8090, reload=True)
