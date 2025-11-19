from app.infrastructure.db.sql_alchemy import engine, Base, create_extensions
from app.infrastructure.db.models import Document, User

def main():
    create_extensions()
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    main()
