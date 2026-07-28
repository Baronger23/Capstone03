"""Dedicated Mandate #19 overload profile.

Run both classes for the graceful-degradation demo, or select one class per
Locust worker to control protected and shedable offered load independently.
"""

import random
import uuid

from locust import HttpUser, between, task

from locustfile import people, products


class BrowseOverloadUser(HttpUser):
    """Low-priority traffic that Envoy is allowed to shed with HTTP 429."""

    weight = 9
    wait_time = between(0.05, 0.15)

    @task(4)
    def list_products(self):
        self.client.get(
            "/api/products",
            name="/api/products [shed_browse]",
        )

    @task(1)
    def homepage(self):
        self.client.get("/", name="/ [shed_browse]")


class ProtectedCheckoutUser(HttpUser):
    """Revenue path that must remain outside the browse token bucket."""

    weight = 1
    wait_time = between(0.5, 1.0)

    @task
    def checkout(self):
        user_id = str(uuid.uuid4())
        product_id = random.choice(products)

        with self.client.get(
            f"/api/products/{product_id}",
            name="/api/products/:id [protected]",
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                response.failure("protected product detail was load-shed")
                return

        with self.client.post(
            "/api/cart",
            name="/api/cart [protected]",
            json={
                "item": {"productId": product_id, "quantity": 1},
                "userId": user_id,
            },
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                response.failure("protected cart was load-shed")
                return
            if not response.ok:
                return

        checkout_person = dict(random.choice(people))
        checkout_person["userId"] = user_id
        with self.client.post(
            "/api/checkout",
            name="/api/checkout [protected]",
            json=checkout_person,
            catch_response=True,
        ) as response:
            if response.status_code == 429:
                response.failure("protected checkout was load-shed")

