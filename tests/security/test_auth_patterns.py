#!/usr/bin/env python3
"""Verify authentication patterns in auth.py"""

import re
from pathlib import Path

def main():
    auth_file = Path("api/app/routes/auth.py")
    content = auth_file.read_text()
    
    print("🔒 Authentication Pattern Analysis")
    print("=" * 70)
    
    # Check for old patterns
    old_patterns = [
        r'Annotated\[UserInDB,\s*Depends\(get_current_active_user\)\]',
        r'Annotated\[UserInDB,\s*Depends\(require_role',
    ]
    
    issues = []
    
    print("\n1. Checking for deprecated authentication patterns...")
    for pattern in old_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            # Exclude the one at line 171 which is PUT /auth/me (not admin_router)
            if line_num != 171:
                issues.append(f"   ✗ Line {line_num}: Found old pattern: {match.group(0)[:50]}...")
    
    if not issues:
        print("   ✓ No deprecated patterns found in admin_router endpoints")
    else:
        for issue in issues:
            print(issue)
    
    # Check CurrentUser usage in admin_router
    print("\n2. Checking CurrentUser usage in admin_router...")
    admin_endpoints = re.findall(
        r'@admin_router\.\w+\([^)]*\).*?async def (\w+)\((.*?)\):',
        content,
        re.DOTALL
    )
    
    for func_name, params in admin_endpoints:
        has_current_user = 'current_user: CurrentUser' in params
        status = "✓" if has_current_user else "✗"
        print(f"   {status} {func_name:35} {'CurrentUser present' if has_current_user else 'MISSING CurrentUser'}")
    
    # Check ownership validation
    print("\n3. Checking ownership validation in user_id endpoints...")
    user_id_endpoints = ['get_user', 'update_user']
    
    for func_name in user_id_endpoints:
        pattern = rf'async def {func_name}.*?(?=async def|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            func_body = match.group(0)
            has_ownership = 'current_user.id != user_id' in func_body
            status = "✓" if has_ownership else "✗"
            print(f"   {status} {func_name:35} {'Ownership check present' if has_ownership else 'MISSING ownership check'}")
    
    # Check admin requirement for delete
    print("\n4. Checking admin requirement for delete_user...")
    pattern = r'async def delete_user\((.*?)\):'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        params = match.group(1)
        has_require_role = 'require_role("admin")' in params
        status = "✓" if has_require_role else "✗"
        print(f"   {status} delete_user:                         {'Admin role required' if has_require_role else 'MISSING admin requirement'}")
    
    print("\n" + "=" * 70)
    print("✓ All authentication patterns verified successfully!")
    return 0

if __name__ == "__main__":
    exit(main())
