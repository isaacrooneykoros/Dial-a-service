from django.urls import path

from apps.catalog.api import views

PREFIX = "console/catalog"

urlpatterns = [
    path(f"{PREFIX}/categories", views.CategoriesView.as_view(), name="catalog-categories"),
    path(
        f"{PREFIX}/categories/<uuid:pk>/update",
        views.CategoryUpdateView.as_view(),
        name="catalog-category-update",
    ),
    path(f"{PREFIX}/services", views.ServicesView.as_view(), name="catalog-services"),
    path(
        f"{PREFIX}/services/reorder",
        views.ServicesReorderView.as_view(),
        name="catalog-services-reorder",
    ),
    path(
        f"{PREFIX}/services/<uuid:pk>/update",
        views.ServiceUpdateView.as_view(),
        name="catalog-service-update",
    ),
    path(
        f"{PREFIX}/services/<uuid:pk>/activate",
        views.ServiceActivateView.as_view(),
        name="catalog-service-activate",
    ),
    path(
        f"{PREFIX}/services/<uuid:pk>/deactivate",
        views.ServiceDeactivateView.as_view(),
        name="catalog-service-deactivate",
    ),
    path(
        f"{PREFIX}/services/<uuid:pk>/prices",
        views.ServicePricesView.as_view(),
        name="catalog-service-prices",
    ),
    path(f"{PREFIX}/modifiers", views.ModifiersView.as_view(), name="catalog-modifiers"),
    path(
        f"{PREFIX}/modifiers/<uuid:pk>/update",
        views.ModifierUpdateView.as_view(),
        name="catalog-modifier-update",
    ),
]
