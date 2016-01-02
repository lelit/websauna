import transaction

from websauna.system.user.usermixin import init_empty_site
from websauna.tests.utils import create_user, EMAIL, PASSWORD


def test_enter_admin(web_server, browser, dbsession):
    """The first user can open the admin page."""

    with transaction.manager:
        u = create_user(dbsession)
        init_empty_site(dbsession, u)
        assert u.is_admin()

    b = browser
    b.visit(web_server + "/login")

    b.fill("username", EMAIL)
    b.fill("password", PASSWORD)
    b.find_by_name("Log_in").click()

    assert b.is_element_visible_by_css("#nav-admin")
    b.find_by_css("#nav-admin").click()

    assert b.is_element_visible_by_css("#admin-main")


def test_non_admin_user_denied(web_server, browser, dbsession):
    """The second user should not see admin link nor get to the admin page."""

    with transaction.manager:
        u = create_user(dbsession)
        init_empty_site(dbsession, u)
        assert u.is_admin()

        u = create_user(dbsession, email="example2@example.com")
        assert not u.is_admin()

    b = browser
    b.visit(web_server + "/login")

    b.fill("username", "example2@example.com")
    b.fill("password", PASSWORD)
    b.find_by_name("Log_in").click()

    assert not b.is_element_visible_by_css("#nav-admin")

    b.visit(web_server + "/admin/")
    assert b.is_element_visible_by_css("#forbidden")
