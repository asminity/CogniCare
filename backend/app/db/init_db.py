from app.db.base import Base
from app.db import models
from app.db.seed import seed_demo_data
from app.db.session import SessionLocal, engine


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_demo_data(db)


if __name__ == "__main__":
    initialize_database()
    print("Cognicare database initialized and demo data loaded.")