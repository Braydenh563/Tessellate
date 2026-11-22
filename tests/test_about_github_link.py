"""Settings, About links to the project (INBOX 904 B51)."""

from tests._app_js import index_html_text

HTML = index_html_text()


def test_about_links_to_the_projects_github() -> None:
    about = HTML[HTML.index('id="settings-about"') :][:4000]
    assert 'id="about-github"' in about
    assert 'href="https://github.com/Braydenh563/Tessellate"' in about
    assert 'rel="noopener"' in about.split('id="about-github"')[1][:200]
