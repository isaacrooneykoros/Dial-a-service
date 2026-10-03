from django.urls import path

from apps.catalog.api import quote_views, views

PREFIX = "console/catalog"

urlpatterns = [
    path("quotes", quote_views.QuoteView.as_view(), name="quotes"),
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
        f"{PREFIX}/import/template",
        views.ImportTemplateView.as_view(),
        name="catalog-import-template",
    ),
    path(
        f"{PREFIX}/import/preview",
        views.ImportPreviewView.as_view(),
        name="catalog-import-preview",
    ),
    path(
        f"{PREFIX}/import/apply",
        views.ImportApplyView.as_view(),
        name="catalog-import-apply",
    ),
    path(
        f"{PREFIX}/modifiers/<uuid:pk>/update",
        views.ModifierUpdateView.as_view(),
        name="catalog-modifier-update",
    ),
]
