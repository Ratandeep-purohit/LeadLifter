import sys
import os

# Add project root to sys.path
sys.path.append(r'd:\projects\CRM GlassEntials')

from app import app, db
from sqlalchemy import text

def add_lead_columns():
    with app.app_context():
        try:
            # Check if columns exist first (optional but safer)
            db.session.execute(text("ALTER TABLE `lead` ADD COLUMN address VARCHAR(255) NULL"))
            db.session.execute(text("ALTER TABLE `lead` ADD COLUMN city VARCHAR(100) NULL"))
            db.session.commit()
            print("Successfully added 'address' and 'city' columns to 'lead' table.")
        except Exception as e:
            db.session.rollback()
            print(f"Error: {e}")

if __name__ == "__main__":
    add_lead_columns()
