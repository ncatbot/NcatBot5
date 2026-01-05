# python
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.rabc import PermissionMatcher, RBACManager


def test_permission_matcher_literal_wildcard_and_regex():
    # literal
    assert PermissionMatcher.match("system.config", "system.config")
    assert not PermissionMatcher.match("system.config", "system.config.read")
    # single-segment *
    assert PermissionMatcher.match("*.config", "system.config")
    assert not PermissionMatcher.match("*.config", "a.b.config")
    # multi-segment **
    assert PermissionMatcher.match("**.log", "app.log")
    assert PermissionMatcher.match("**.log", "a.b.c.log")
    # regex inside []
    assert PermissionMatcher.match("[a\\d+\\.txt]", "a123.txt")  # regex matches
    # invalid regex returns False (should not raise)
    assert not PermissionMatcher.match("[[invalid", "anything")


def test_role_permissions_and_inheritance_and_tree():
    m = RBACManager("m1")
    parent = m.create_role("parent")
    child = m.create_role("child")
    parent.add_permission("system.config.read")
    child.inherit_from(parent)
    assert child.has_permission("system.config.read")
    # cyclic inheritance should not infinite loop
    a = m.create_role("A")
    b = m.create_role("B")
    a.inherit_from(b)
    b.inherit_from(a)
    a.add_permission("x.y")
    assert b.has_permission("x.y")  # finds via A->B cycle guard
    # permission tree: nested structure and regex preserved as single segment
    r = m.create_role("r")
    r.add_permission("a.b.c")
    r.add_permission("[regex.*]")
    tree = r.get_permission_tree()
    assert "a" in tree and "b" in tree["a"] and "c" in tree["a"]["b"]
    assert "[regex.*]" in tree  # regex kept as one key


def test_user_can_whitelist_blacklist_and_roles_precedence():
    m = RBACManager("m2")
    role = m.create_role("role")
    role.add_permission("a.b")
    u = m.create_user("alice")
    u.add_role(role)
    # role grants permission
    assert u.can("a.b")
    # whitelist grants other permission
    u.permit("x.*")
    assert u.can("x.y")
    # blacklist vetoes even if role or whitelist matches
    u.permit("a.b")  # whitelist present
    u.deny("a.*")  # blacklist should override
    assert not u.can("a.b")
    # blacklist that doesn't match should not veto unrelated perms
    assert u.can("x.y")


def test_user_get_permission_tree_merging_and_status():
    m = RBACManager("m3")
    r1 = m.create_role("r1")
    r1.add_permission("s.t.r")
    r1.add_permission("[re\\.ex]")
    u = m.create_user("bob")
    u.add_role(r1)
    u.permit("s.t.allowed")
    u.deny("s.t.r")  # explicit denial should show status False
    tree = u.get_permission_tree()
    # role perm present and then overridden by blacklist
    assert "s" in tree and "t" in tree["s"]
    assert "r" in tree["s"]["t"] and tree["s"]["t"]["r"]["__status__"] is False
    assert (
        "allowed" in tree["s"]["t"] and tree["s"]["t"]["allowed"]["__status__"] is True
    )
    # regex permission preserved as single key in user tree
    assert "[re\\.ex]" in tree


def test_manager_save_and_load_roundtrip(tmp_path: Path):
    m = RBACManager("save_test")
    r = m.create_role("admin")
    r.add_permission("sys.*")
    guest = m.create_role("guest")
    guest.add_permission("read.public")
    r.inherit_from(guest)
    u = m.create_user("carol")
    u.add_role(r)
    u.permit("override.allow")
    u.deny("sys.secret")
    fp = tmp_path / "rbac_test.json"
    m.save_to_file(str(fp))
    loaded = RBACManager.load_from_file(str(fp))
    # roles and users present
    lr = loaded.get_role("admin")
    assert lr is not None
    lu = loaded.get_user("carol")
    assert lu is not None
    # permission inheritance and checks preserved
    assert lu.can("read.public")
    assert lu.can("sys.something")
    assert not lu.can("sys.secret")


def test_cross_manager_compatibility_checks():
    m1 = RBACManager("m1")
    m2 = RBACManager("m2")
    r2 = m2.create_role("r2")
    u1 = m1.create_user("u1")
    # adding role from another manager should raise
    with pytest.raises(RuntimeError):
        u1.add_role(r2)
    r1 = m1.create_role("r1")
    # inheritance across managers should raise
    with pytest.raises(RuntimeError):
        r1.inherit_from(r2)
