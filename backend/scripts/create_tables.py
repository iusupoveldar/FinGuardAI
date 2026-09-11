from app.database.base import Base
from app.database.connection import engine

from app.models.customer import Customer
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.alert import Alert
from app.models.alert import AlertTransaction



def create_tables():

    print("Creating tables...")


    Base.metadata.create_all(
        bind=engine
    )


    print("Done")


if __name__ == "__main__":

    create_tables()