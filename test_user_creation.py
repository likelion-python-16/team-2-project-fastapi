#!/usr/bin/env python3

"""Test script to reproduce the User creation error"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.models.user import User

def test_user_creation():
    print("Testing User model creation...")
    db = SessionLocal()
    
    try:
        # Try creating a minimal user
        user = User(
            username="test_user",
            email="test@example.com", 
            password_hash="dummy_hash",
            name="Test User",
            introduction=""  # Explicitly set to empty string
        )
        
        print(f"User object created: {user}")
        print(f"User.created_at attribute: {getattr(user, 'created_at', 'NOT FOUND')}")
        print(f"User.updated_at attribute: {getattr(user, 'updated_at', 'NOT FOUND')}")
        
        # Try adding to database
        db.add(user)
        print("User added to session")
        
        # Try committing
        db.commit()
        print("✅ User creation successful!")
        print(f"User ID: {user.id}")
        print(f"Created at: {user.created_at}")
        print(f"Updated at: {user.updated_at}")
        
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        print(f"Error type: {type(e)}")
        db.rollback()
        
        # Let's see what columns are actually in the users table
        try:
            result = db.execute("DESCRIBE users")
            print("\nActual users table structure:")
            for row in result:
                print(f"  {row}")
        except Exception as desc_error:
            print(f"Could not describe table: {desc_error}")
            
    finally:
        db.close()

if __name__ == "__main__":
    test_user_creation()