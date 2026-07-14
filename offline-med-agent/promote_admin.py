"""
One-off CLI to promote an existing user to admin.
Use this only if you have accounts but no admin exists yet
(e.g. everyone signed up via self-signup, which always creates 'user' role).

Run: python promote_admin.py
"""
import auth_db

if __name__ == "__main__":
    auth_db.init_db()
    users = auth_db.list_users()

    if not users:
        print("No users exist yet. Just run the app and use the first-run setup screen instead.")
    else:
        print("Existing users:")
        for u in users:
            print(f"  - {u['username']} (role: {u['role']})")

        target = input("\nUsername to promote to admin: ").strip()
        matched = next((u for u in users if u["username"] == target), None)

        if not matched:
            print(f"No user named '{target}' found.")
        elif matched["role"] == "admin":
            print(f"'{target}' is already an admin.")
        else:
            with auth_db.get_connection() as conn:
                conn.execute("UPDATE users SET role = 'admin' WHERE username = ?", (target,))
            auth_db.log_action(target, "role_changed", detail="promoted to admin via CLI script")
            print(f"'{target}' is now an admin. Log out and back in for the role to take effect in the UI.")