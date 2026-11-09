import db

if __name__ == "__main__":
    print("aplicadas:", db.migrate() or "ninguna (ya estaban)")
