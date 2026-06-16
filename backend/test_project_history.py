"""Test project history tracking functionality."""

import json
import time
from pathlib import Path
from app.memory.session_memory import (
    add_to_project_history,
    get_project_from_history,
    get_projects_history,
    load_session_memory,
)

# Test data
TEST_SESSION_ID = "test-session-123"

def test_project_history():
    """Test adding and retrieving project history."""
    
    print("=" * 60)
    print("Testing Project History Tracking")
    print("=" * 60)
    
    # Add 5 projects to history
    projects = [
        {"id": "proj1", "name": "Project Alpha"},
        {"id": "proj2", "name": "Project Beta"},
        {"id": "proj3", "name": "Project Gamma"},
        {"id": "proj4", "name": "Project Delta"},
        {"id": "proj5", "name": "Project Epsilon"},
    ]
    
    print("\n1. Adding 5 projects to history...")
    for proj in projects:
        add_to_project_history(
            session_id=TEST_SESSION_ID,
            project_id=proj["id"],
            project_name=proj["name"],
            portal_id="portal123",
        )
        print(f"   Added: {proj['name']} (ID: {proj['id']})")
        time.sleep(0.1)  # Small delay to ensure different timestamps
    
    # Retrieve all history
    print("\n2. Retrieving full project history...")
    history = get_projects_history(TEST_SESSION_ID)
    print(f"   Total projects in history: {len(history)}")
    
    # Display history (most recent first)
    print("\n3. Project history (most recent first):")
    for idx, proj in enumerate(history, 1):
        print(f"   #{idx}: {proj['name']} (ID: {proj['id']})")
    
    # Get specific project by index (0-based)
    print("\n4. Accessing specific projects from history:")
    for idx in [0, 4]:
        proj = get_project_from_history(TEST_SESSION_ID, idx)
        if proj:
            print(f"   Project #{idx + 1}: {proj['name']} (ID: {proj['id']})")
    
    # Show what the LLM would see
    print("\n5. What LLM sees (first 10 projects):")
    print("   User's recent projects (most recent first):")
    for idx, proj in enumerate(history[:10], 1):
        print(f"   {idx}. {proj.get('name', 'Unknown')} (ID: {proj.get('id')})")
    
    # Verify: "Which is my 5th project?"
    print("\n6. Answering 'Which is my 5th project?':")
    fifth_project = get_project_from_history(TEST_SESSION_ID, 4)  # 0-based index
    if fifth_project:
        print(f"   Answer: Your 5th most recent project is '{fifth_project['name']}'")
    
    print("\n" + "=" * 60)
    print("✓ Test completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    test_project_history()
