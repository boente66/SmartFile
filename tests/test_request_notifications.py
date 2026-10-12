import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication,QStackedWidget

from app.database.database import Database
from app.services.request_notification_service import RequestNotificationService,request_stage
from app.views.delivery_workspace_view import DeliveryWorkspaceView

APP = QApplication.instance() or QApplication([])


def request(identifier,org=1,user=2,status='OPEN'):
    return SimpleNamespace(id=identifier,organization_id=org,assigned_to_user_id=user,
                           requested_by_user_id=3,status=status,title='Documento',updated_at='now')


def test_reading_and_dedup_survive_refresh_restart_and_org_switch(tmp_path):
    db=Database(str(tmp_path/'db.sqlite'))
    service=RequestNotificationService(db)
    assert not service.observe(1,2,[request(1)])
    assert service.unread=={1}
    assert service.observe(1,2,[request(1),request(2)])=={2}
    assert not service.observe(1,2,[request(1,status='IN_PROGRESS'),request(2)])
    service.mark_read(1)
    assert service.unread=={2}
    assert not service.observe(1,2,[request(1),request(2)])
    service.preferences(False,False)
    restarted=RequestNotificationService(db)
    assert not restarted.observe(1,2,[request(1),request(2)])
    assert not restarted.sound and not restarted.animation
    assert restarted.unread=={2}
    assert not restarted.observe(9,2,[request(8,org=9)])
    assert restarted.unread=={8}
    assert not restarted.observe(1,2,[request(1),request(2)])
    assert restarted.unread=={2}
    assert restarted.observe(1,2,[request(1),request(2),request(3)])=={3}
    assert not restarted.observe(1,2,[request(4,user=9),request(5,org=8)])
    db.close()


def test_flow_click_counters_badge_and_secondary_panels():
    app=QApplication.instance() or QApplication([])
    view=DeliveryWorkspaceView()
    requests=[request(i,status=status) for i,status in enumerate(('OPEN','IN_PROGRESS','ATTENDED','DELIVERING','COMPLETED','CANCELLED'),1)]
    view.set_requests(requests,2);view.set_unread({1})
    assert isinstance(view.tabs,QStackedWidget)
    assert view.flow.counts==[1,1,1,1,2]
    assert view.flow.badge==1
    observed=[];view.request_read.connect(observed.append)
    view.requests_list.setCurrentRow(0)
    assert observed==[1]
    for index,count in ((1,1),(2,1),(4,2)):
        view.flow.buttons[index].click()
        assert view.requests_list.count()==count
    view.select_tab('received')
    assert view.tabs.currentWidget()==view.inbox_list.parentWidget()
    view.flow.alert();assert view.flow.timer.isActive()
    for _ in range(30):view.flow._animate()
    assert not view.flow.timer.isActive()
    view.close()


def test_operational_status_is_independent():
    assert request_stage('ATTENDED')==2
    assert request_stage('DELIVERING')==3
    assert request_stage('COMPLETED')==4


def test_overdue_keeps_its_operational_stage():
    app=QApplication.instance() or QApplication([])
    view=DeliveryWorkspaceView()
    overdue=request(1,status='OVERDUE');overdue.operational_status='ATTENDED'
    view.set_requests([overdue],2)
    assert view.flow.counts==[0,0,1,0,0]
    assert request_stage('DELIVERED')==3
    view.close()


def test_controller_alerts_only_new_ids_and_honors_preferences():
    from app.controllers.document_delivery_controller import DocumentDeliveryController
    events=[]
    class Notifications:
        sound=True;animation=True;unread=set()
        known=set()
        def observe(self,org,user,requests):
            ids={r.id for r in requests};new=ids-self.known;self.known|=ids;self.unread|=new;return new
    controller=DocumentDeliveryController.__new__(DocumentDeliveryController)
    controller._require_available=lambda:None
    controller.documents=SimpleNamespace(active_organization_id=1)
    controller.context=SimpleNamespace(current_user=SimpleNamespace(id=2))
    rows=[request(1)]
    controller.requests=SimpleNamespace(list_requests=lambda _:rows)
    controller.notifications=Notifications()
    controller._alert_sound=SimpleNamespace(play=lambda:events.append('sound'))
    controller._request_fingerprint=None;controller.main_view=None
    controller.view=SimpleNamespace(set_alert_preferences=lambda *args:None,set_requests=lambda *args:None,
        set_unread=lambda *args:None,flow=SimpleNamespace(alert=lambda:events.append('animation')))
    controller._poll_requests();assert events==['sound','animation']
    controller._poll_requests();rows[0].status='IN_PROGRESS';controller._poll_requests()
    assert len(events)==2
    rows.append(request(2));controller._poll_requests();assert len(events)==4
    controller.notifications.sound=False;rows.append(request(3));controller._poll_requests()
    assert events[-1]=='animation' and len(events)==5
    controller.notifications.animation=False;rows.append(request(4));controller._poll_requests()
    assert len(events)==5
