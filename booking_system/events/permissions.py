from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Доступ только для ADMIN"""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.roles.filter(role__name="ADMIN").exists()
        )


class IsOrganizer(BasePermission):
    """
    Организатор может создавать события,
    но изменять и удалять — только свои.
    """
    def has_permission(self, request, view):
        # организатор может создавать события
        return (
            request.user.is_authenticated and
            request.user.roles.filter(role__name="ORGANIZER").exists()
        )

    def has_object_permission(self, request, view, obj):
        # админ может всё
        if request.user.roles.filter(role__name="ADMIN").exists():
            return True

        # организатор может менять только свои события
        return obj.organizer == request.user


class IsModerator(BasePermission):
    """
    Модератор может изменять и удалять отзывы.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and (
                request.user.roles.filter(role__name="MODERATOR").exists() or
                request.user.roles.filter(role__name="ADMIN").exists()
            )
        )

    def has_object_permission(self, request, view, obj):
        # модератор и админ могут редактировать/удалять любой отзыв
        return self.has_permission(request, view)
