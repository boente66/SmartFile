import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from app.views.cloud_authentication_dialog import CloudAuthenticationDialog

_APPLICATION = None


def app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def test_cloud_dialog_exposes_url_copy_and_requires_code():
    qt = app()
    url = "https://login.example.test/oauth/authorize?client_id=smartfile"
    dialog = CloudAuthenticationDialog("ONEDRIVE", url)
    assert dialog.url_edit.text() == url
    assert dialog.url_edit.isReadOnly()
    dialog.copy_link()
    assert qt.clipboard().text() == url
    dialog._accept_if_valid()
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Cole o código" in dialog.status_label.text()
    dialog.code_edit.setText("authorization-code")
    dialog._accept_if_valid()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_cloud_dialog_identifies_google_drive():
    app()
    dialog = CloudAuthenticationDialog("GOOGLE_DRIVE", "https://accounts.google.test/o/oauth2/v2/auth")
    assert "Google Drive" in dialog.windowTitle()
    assert dialog.authorization_code() == ""
