"""
Tests for the task and purchase order endpoints.

Both resources keep their state in module-level lists in main.py rather than a
database, so every test here starts from a clean slate via the reset fixture
below. Without it a purchase order raised by one test would make the next one
fail with a 409, and the suite would only pass in a particular order.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_runtime_state():
    """Clear the in-memory tasks and purchase orders around each test."""
    def clear():
        main.tasks.clear()
        main.purchase_orders.clear()
        main.next_task_id = 1
        for item in main.backlog_items:
            item["has_purchase_order"] = False

    clear()
    yield
    clear()


class TestTaskEndpoints:
    """Test suite for /api/tasks."""

    def test_get_tasks_returns_list(self, client):
        """Test that the tasks endpoint answers with a list rather than a 404."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_task(self, client):
        """Test creating a task returns it with a generated id and pending status."""
        response = client.post("/api/tasks", json={
            "title": "Audit Tokyo warehouse",
            "priority": "high",
            "dueDate": "2026-08-15"
        })
        assert response.status_code == 201

        task = response.json()
        assert task["title"] == "Audit Tokyo warehouse"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2026-08-15"
        assert task["status"] == "pending"
        assert task["id"]

        client.delete(f"/api/tasks/{task['id']}")

    def test_created_task_id_does_not_collide_with_client_demo_tasks(self, client):
        """Ids must not be bare 1-3: the client merges these with its own demo tasks."""
        response = client.post("/api/tasks", json={
            "title": "Check reorder points",
            "dueDate": "2026-08-15"
        })
        task = response.json()
        assert task["id"] not in ("1", "2", "3", 1, 2, 3)

        client.delete(f"/api/tasks/{task['id']}")

    def test_create_task_defaults_to_medium_priority(self, client):
        """Test that priority is optional."""
        response = client.post("/api/tasks", json={
            "title": "Update supplier contacts",
            "dueDate": "2026-09-01"
        })
        assert response.status_code == 201
        assert response.json()["priority"] == "medium"

        client.delete(f"/api/tasks/{response.json()['id']}")

    def test_create_task_rejects_blank_title(self, client):
        """Test that a whitespace-only title is rejected."""
        response = client.post("/api/tasks", json={
            "title": "   ",
            "dueDate": "2026-08-15"
        })
        assert response.status_code == 400

    def test_created_task_appears_in_listing(self, client):
        """Test that a created task is returned by the listing endpoint."""
        created = client.post("/api/tasks", json={
            "title": "Reconcile Q3 spending",
            "dueDate": "2026-08-20"
        }).json()

        listed = client.get("/api/tasks").json()
        assert any(t["id"] == created["id"] for t in listed)

        client.delete(f"/api/tasks/{created['id']}")

    def test_toggle_task_flips_status_both_ways(self, client):
        """Test that PATCH toggles between pending and completed."""
        created = client.post("/api/tasks", json={
            "title": "Approve London orders",
            "dueDate": "2026-08-05"
        }).json()

        assert client.patch(f"/api/tasks/{created['id']}").json()["status"] == "completed"
        assert client.patch(f"/api/tasks/{created['id']}").json()["status"] == "pending"

        client.delete(f"/api/tasks/{created['id']}")

    def test_toggle_missing_task_returns_404(self, client):
        """Test toggling an unknown task id."""
        response = client.patch("/api/tasks/task-does-not-exist")
        assert response.status_code == 404

    def test_delete_task_removes_it(self, client):
        """Test that a deleted task no longer shows up in the listing."""
        created = client.post("/api/tasks", json={
            "title": "Archive old forecasts",
            "dueDate": "2026-08-11"
        }).json()

        assert client.delete(f"/api/tasks/{created['id']}").status_code == 200

        listed = client.get("/api/tasks").json()
        assert all(t["id"] != created["id"] for t in listed)

    def test_delete_missing_task_returns_404(self, client):
        """Test deleting an unknown task id."""
        response = client.delete("/api/tasks/task-does-not-exist")
        assert response.status_code == 404


class TestPurchaseOrderEndpoints:
    """Test suite for /api/purchase-orders."""

    @pytest.fixture
    def backlog_item_id(self, client):
        """Id of an existing backlog item to raise purchase orders against."""
        backlog = client.get("/api/backlog").json()
        assert len(backlog) > 0, "Backlog fixture data is required for these tests"
        return backlog[0]["id"]

    def test_create_purchase_order(self, client, backlog_item_id):
        """Test raising a purchase order against a backlog item."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": backlog_item_id,
            "supplier_name": "Acme Parts",
            "quantity": 350,
            "unit_cost": 12.5,
            "expected_delivery_date": "2026-08-20",
            "notes": "Covers the shortfall"
        })
        assert response.status_code == 201

        purchase_order = response.json()
        assert purchase_order["backlog_item_id"] == backlog_item_id
        assert purchase_order["supplier_name"] == "Acme Parts"
        assert purchase_order["quantity"] == 350
        assert purchase_order["status"] == "Pending"
        assert purchase_order["created_date"]

    def test_create_purchase_order_flags_the_backlog_item(self, client, backlog_item_id):
        """Test that the backlog item is marked so the UI stops offering a second PO."""
        client.post("/api/purchase-orders", json={
            "backlog_item_id": backlog_item_id,
            "supplier_name": "Acme Parts",
            "quantity": 100,
            "unit_cost": 9.0,
            "expected_delivery_date": "2026-08-20"
        })

        backlog = client.get("/api/backlog").json()
        item = next(b for b in backlog if b["id"] == backlog_item_id)
        assert item["has_purchase_order"] is True

    def test_second_purchase_order_for_same_item_is_rejected(self, client, backlog_item_id):
        """Test that a backlog item cannot accumulate two purchase orders."""
        payload = {
            "backlog_item_id": backlog_item_id,
            "supplier_name": "Acme Parts",
            "quantity": 50,
            "unit_cost": 4.0,
            "expected_delivery_date": "2026-08-20"
        }
        client.post("/api/purchase-orders", json=payload)

        response = client.post("/api/purchase-orders", json=payload)
        assert response.status_code == 409

    def test_get_purchase_order_by_backlog_item(self, client, backlog_item_id):
        """Test looking a purchase order up by the backlog item it covers."""
        client.post("/api/purchase-orders", json={
            "backlog_item_id": backlog_item_id,
            "supplier_name": "Globex Supply",
            "quantity": 40,
            "unit_cost": 5.25,
            "expected_delivery_date": "2026-09-02"
        })

        response = client.get(f"/api/purchase-orders/{backlog_item_id}")
        assert response.status_code == 200
        assert response.json()["backlog_item_id"] == backlog_item_id

    def test_get_purchase_order_for_uncovered_item_returns_404(self, client):
        """Test that a backlog item without a purchase order returns 404."""
        response = client.get("/api/purchase-orders/no-such-backlog-item")
        assert response.status_code == 404

    def test_create_purchase_order_for_missing_backlog_item_returns_404(self, client):
        """Test that the backlog item has to exist."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": "no-such-backlog-item",
            "supplier_name": "Acme Parts",
            "quantity": 10,
            "unit_cost": 1.0,
            "expected_delivery_date": "2026-08-20"
        })
        assert response.status_code == 404

    def test_create_purchase_order_rejects_non_positive_quantity(self, client, backlog_item_id):
        """Test that a zero quantity purchase order is rejected."""
        response = client.post("/api/purchase-orders", json={
            "backlog_item_id": backlog_item_id,
            "supplier_name": "Acme Parts",
            "quantity": 0,
            "unit_cost": 1.0,
            "expected_delivery_date": "2026-08-20"
        })
        assert response.status_code == 400
