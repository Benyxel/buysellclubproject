from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django.db.models import Q
from django.contrib.auth.hashers import make_password, check_password
import logging

logger = logging.getLogger(__name__)
from .serializers import (
    UserCreateSerializer,
    UserModelSerializer,
    CustomTokenObtainPairSerializer,
    TrackingSerializer,
    ShippingMarkSerializer,
    ShippingRateSerializer,
    ShippingAddressSerializer,
    DefaultBaseAddressSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    ContainerSerializer,
    ContainerDetailSerializer,
    InvoiceSerializer,
    AlipayPaymentSerializer,
    AlipayExchangeRateSerializer,
    DashboardTabSerializer,
    ProductSerializer,
    ProductReviewSerializer,
    OrderSerializer,
    CategorySerializer,
    ProductTypeSerializer,
    Buy4meRequestSerializer,
)

from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from .models import (
    UserModel,
    Container,
    Tracking,
    ShippingMark,
    ShippingRate,
    ShippingAddress,
    DefaultBaseAddress,
    EmailNotification,
    LoginOTP,
    PasswordResetOTP,
    Invoice,
    InvoiceItem,
    AlipayPayment,
    AlipayExchangeRate,
    DashboardTab,
    Product,
    ProductReview,
    Order,
    Category,
    ProductType,
    Buy4meRequest,
)
from .buy4me_views import (
    UserBuy4meRequestListView,
    UserBuy4meRequestDetailView,
    AdminBuy4meRequestListView,
    AdminBuy4meRequestDetailView,
    AdminBuy4meRequestStatusView,
    AdminBuy4meRequestTrackingView,
    AdminBuy4meRequestInvoiceView,
)
from .quick_order_views import (
    QuickOrderProductListView,
    AdminQuickOrderProductListView,
    AdminQuickOrderProductDetailView,
)
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.db.utils import IntegrityError
from django.db.models import Sum

# Create your views here.


def is_admin_user(user):
    """Check if a user is an admin (either is_staff or has role='admin' in UserModel)."""
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    try:
        profile = UserModel.objects.get(username=user.username)
        return profile.role == "admin"
    except UserModel.DoesNotExist:
        return False


from rest_framework import generics, status
from rest_framework.response import Response
from .models import UserModel
from .serializers import (
    UserCreateSerializer,
    UserModelSerializer,
    TrackingSerializer,
    ShippingMarkSerializer,
)


class UserCreateView(generics.CreateAPIView):
    queryset = UserModel.objects.all()
    serializer_class = UserCreateSerializer

    def create(self, request):
        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()

            return Response(
                {
                    "message": "User created successfully! 🎉",
                    "username": user.username,
                    "email": user.email,
                    "status": "You can now login with your credentials",
                },
                status=status.HTTP_201_CREATED,
            )
        except ValidationError as e:
            # Handle validation errors with detailed messages
            return Response(
                e.detail if hasattr(e, "detail") else {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Handle unexpected errors
            return Response(
                {"error": "An error occurred during registration. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class UserListView(generics.ListAPIView):
    queryset = UserModel.objects.all()
    serializer_class = UserModelSerializer
    permission_classes = [IsAuthenticated]


class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = UserModel.objects.all()
    serializer_class = UserModelSerializer
    permission_classes = [IsAuthenticated]

    # DELETE FUNCTION


class UserDeleteView(generics.DestroyAPIView):
    queryset = UserModel.objects.all()
    serializer_class = UserModelSerializer
    permission_classes = [IsAuthenticated]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Determine if the requester is an admin (via Django is_staff or our UserModel.role)
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False

        if not is_admin:
            return Response(
                {
                    "error": "Permission denied! ❌",
                    "message": "Only admins can delete users.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent deleting other admins
        if instance.role == "admin":
            return Response(
                {
                    "error": "Cannot delete admin users! ❌",
                    "message": "Admin users cannot be deleted for security reasons.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent deleting self
        if instance.username == request.user.username:
            return Response(
                {
                    "error": "Cannot delete your own account! ❌",
                    "message": "Please use account settings to delete your own account.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        deleted_user_info = {
            "id": instance.id,
            "username": instance.username,
            "email": instance.email,
            "role": instance.role,
        }

        # Also remove corresponding Django auth user if present
        try:
            auth_user = User.objects.get(username=instance.username)
            auth_user.delete()
        except User.DoesNotExist:
            pass

        self.perform_destroy(instance)

        return Response(
            {
                "message": "User account deleted successfully! ✅",
                "deleted_user": deleted_user_info,
                "deleted_by": request.user.username,
            },
            status=status.HTTP_200_OK,
        )


# UPDATE FUNCTION


class UserUpdateView(generics.UpdateAPIView):
    queryset = UserModel.objects.all()
    serializer_class = UserModelSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        # Determine if requester is admin
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False

        # Users can only update their own profile, unless they are admin
        if instance.username != request.user.username and not is_admin:
            return Response(
                {
                    "error": "Permission denied! ❌",
                    "message": "You can only update your own profile.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Continue with update using serializer
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Keep Django auth user's is_staff in sync with role changes
        if "role" in request.data:
            try:
                auth_user = User.objects.get(username=instance.username)
                auth_user.is_staff = request.data.get("role") == "admin"
                auth_user.save(update_fields=["is_staff"])
            except User.DoesNotExist:
                pass

        return Response(
            {"message": "User updated successfully! ✅", "user": serializer.data},
            status=status.HTTP_200_OK,
        )


class ProductListView(generics.ListAPIView):
    """Public product list endpoint with optional filtering/querying."""

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    pagination_class = PageNumberPagination
    
    def list(self, request, *args, **kwargs):
        """Override list to add debugging info."""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            serializer = self.get_serializer(queryset, many=True)
            logger.info(f"ProductListView: Returning {len(serializer.data)} products")
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error in ProductListView.list: {e}", exc_info=True)
            return Response(
                {"error": str(e), "detail": "Error fetching products"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get_queryset(self):
        try:
            qs = Product.objects.filter(is_active=True)
            q = self.request.query_params.get("q")
            category = self.request.query_params.get("category")
            ptype = self.request.query_params.get("type")

            if q:
                qs = qs.filter(
                    Q(name__icontains=q)
                    | Q(description__icontains=q)
                    | Q(slug__icontains=q)
                )
            if category:
                qs = qs.filter(category__iexact=category)
            if ptype:
                qs = qs.filter(product_type__iexact=ptype)

            return qs.order_by("-created_at")
        except Exception as e:
            logger.error(f"Error in ProductListView.get_queryset: {e}")
            return Product.objects.none()

    def post(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication required. Please log in."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Only admin/staff users may create products
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
            except Exception as e:
                logger.error(f"Error checking admin status: {e}")
                is_admin = False

        if not is_admin:
            return Response(
                {"detail": "You do not have permission to create products. Admin access required."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            obj = serializer.save()
            return Response(ProductSerializer(obj).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            # Return detailed validation errors
            return Response(
                e.detail if hasattr(e, "detail") else {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error creating product: {e}")
            return Response(
                {"detail": f"Error creating product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve a product by slug."""

    serializer_class = ProductSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"
    queryset = Product.objects.all()

    def update(self, request, *args, **kwargs):
        # Only admin/staff users may update products
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False

        if not is_admin:
            return Response(status=status.HTTP_403_FORBIDDEN)

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Only admin/staff users may delete products
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False

        if not is_admin:
            return Response(status=status.HTTP_403_FORBIDDEN)

        return super().destroy(request, *args, **kwargs)


class ProductReviewListView(generics.ListCreateAPIView):
    """List reviews for a product or create a new review."""
    
    serializer_class = ProductReviewSerializer
    permission_classes = [AllowAny]
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        product_slug = self.request.query_params.get('product')
        product_id = self.request.query_params.get('product_id')
        
        if product_slug:
            try:
                product = Product.objects.get(slug=product_slug)
                return ProductReview.objects.filter(
                    product=product,
                    is_approved=True
                )
            except Product.DoesNotExist:
                return ProductReview.objects.none()
        elif product_id:
            try:
                product = Product.objects.get(id=product_id)
                return ProductReview.objects.filter(
                    product=product,
                    is_approved=True
                )
            except Product.DoesNotExist:
                return ProductReview.objects.none()
        
        return ProductReview.objects.filter(is_approved=True)
    
    def perform_create(self, serializer):
        # Get the user from the request
        user = None
        if self.request.user and self.request.user.is_authenticated:
            try:
                user = UserModel.objects.get(username=self.request.user.username)
            except UserModel.DoesNotExist:
                pass
        
        if not user:
            raise PermissionDenied("You must be logged in to submit a review.")
        
        # Check if user already reviewed this product
        product = serializer.validated_data.get('product')
        existing_review = ProductReview.objects.filter(
            product=product,
            user=user
        ).first()
        
        if existing_review:
            # Update existing review instead of creating new one
            serializer.instance = existing_review
            serializer.save(user=user)
        else:
            serializer.save(user=user)


class ProductReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a review."""
    
    serializer_class = ProductReviewSerializer
    queryset = ProductReview.objects.all()
    
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def update(self, request, *args, **kwargs):
        review = self.get_object()
        
        # Only the review owner or admin can update
        user = None
        if request.user and request.user.is_authenticated:
            try:
                user = UserModel.objects.get(username=request.user.username)
            except UserModel.DoesNotExist:
                pass
        
        if not user:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        
        if review.user != user and not is_admin:
            return Response(
                {"detail": "You can only edit your own reviews."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        
        user = None
        if request.user and request.user.is_authenticated:
            try:
                user = UserModel.objects.get(username=request.user.username)
            except UserModel.DoesNotExist:
                pass
        
        if not user:
            return Response(
                {"detail": "Authentication required."},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        is_admin = bool(getattr(request.user, "is_staff", False))
        if not is_admin:
            try:
                req_profile = UserModel.objects.get(username=request.user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        
        if review.user != user and not is_admin:
            return Response(
                {"detail": "You can only delete your own reviews."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)


class CurrentUserView(APIView):
    """Return the current authenticated user's profile from UserModel."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Determine admin status from Django auth user
        django_user = getattr(request, "user", None)
        is_admin_django = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )

        try:
            profile = UserModel.objects.get(username=request.user.username)
            data = UserModelSerializer(profile).data
            # If Django says admin but profile role isn't admin, surface admin role in response
            if is_admin_django and data.get("role") != "admin":
                data["role"] = "admin"
            # Expose whether the underlying Django user is a superuser so front-end can
            # distinguish superadmins from regular admins.
            data["is_superuser"] = getattr(request.user, "is_superuser", False)
            # Ensure username/email are present even if serializer is minimal
            if "username" not in data:
                data["username"] = request.user.username
            if "email" not in data:
                data["email"] = getattr(request.user, "email", "")
            return Response(data, status=status.HTTP_200_OK)
        except UserModel.DoesNotExist:
            # No profile in UserModel; return a minimal payload so clients can still gate by admin
            return Response(
                {
                    "username": request.user.username,
                    "email": getattr(request.user, "email", ""),
                    "role": "admin" if is_admin_django else "user",
                    "is_superuser": getattr(request.user, "is_superuser", False),
                },
                status=status.HTTP_200_OK,
            )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class DashboardTabsView(APIView):
    """Return dashboard tabs available to the requesting user.

    Superusers receive all active tabs. Regular users receive tabs that are
    active and either assigned directly to them, assigned to one of their
    groups, or (optionally) tabs with no assignment (treated as public to staff).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            qs = DashboardTab.objects.prefetch_related("users", "groups").filter(is_active=True)
            # Superusers get everything
            if getattr(user, "is_superuser", False):
                serializer = DashboardTabSerializer(
                    qs.order_by("order", "name"), many=True, context={"request": request}
                )
                return Response(serializer.data)

            # Only staff (admins) should receive tabs assigned to them by superadmin.
            # Non-staff regular users get no dashboard tabs from this endpoint.
            is_staff = getattr(user, "is_staff", False)
            if not is_staff:
                # Fall back to custom UserModel role if Django auth isn't marked as staff
                try:
                    profile = UserModel.objects.get(username=user.username)
                    is_staff = profile.role == "admin"
                except UserModel.DoesNotExist:
                    is_staff = False

            if not is_staff:
                return Response([])

            # Admin users should only see tabs that are assigned to them
            # Check for direct user assignment
            user_tabs = qs.filter(users=user)
            # Check for group assignments
            user_groups = user.groups.all()
            group_tabs = qs.filter(groups__in=user_groups) if user_groups.exists() else qs.none()
            # Combine both (using union to avoid duplicates)
            assigned_tabs = (user_tabs | group_tabs).distinct()
            
            serializer = DashboardTabSerializer(
                assigned_tabs.order_by("order", "name"), many=True, context={"request": request}
            )
            return Response(serializer.data)
        except Exception as e:
            logger.exception("Error in DashboardTabsView.get: %s", e)
            return Response(
                {"error": "Failed to fetch dashboard tabs", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DashboardTabsAllView(APIView):
    """Return all dashboard tabs (superuser only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)
        qs = DashboardTab.objects.prefetch_related("users", "groups").all().order_by("order", "name")
        serializer = DashboardTabSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        """Create a new DashboardTab (superuser only).

        Expected payload: { name, slug, description?, order? }
        """
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)

        data = request.data or {}
        name = (data.get("name") or "").strip()
        slug = (data.get("slug") or "").strip()
        description = data.get("description", "")
        order = data.get("order")

        if not name or not slug:
            return Response(
                {"error": "name and slug are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if DashboardTab.objects.filter(slug=slug).exists():
            return Response(
                {"error": "A tab with that slug already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tab = DashboardTab.objects.create(
                name=name,
                slug=slug,
                description=description or "",
                order=order or 0,
                is_active=True,
            )
        except Exception as e:
            logger.exception("Failed to create DashboardTab: %s", e)
            return Response(
                {"error": "Failed to create tab"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = DashboardTabSerializer(tab, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DashboardTabsUserView(APIView):
    """Get the list of tab slugs assigned to a specific user (superuser only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, user_id=None):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)
        # Allow either a Django auth.User id or a custom UserModel id to be passed.
        user = None
        try:
            user = User.objects.get(id=user_id)
        except (User.DoesNotExist, ValueError, TypeError):
            # Not a Django User id — try resolving via UserModel (custom profile)
            try:
                profile = UserModel.objects.get(id=user_id)
                user = User.objects.filter(username=profile.username).first()
            except (UserModel.DoesNotExist, ValueError, TypeError):
                user = None

        if not user:
            return Response(status=status.HTTP_404_NOT_FOUND)

        qs = DashboardTab.objects.filter(is_active=True, users=user).order_by(
            "order", "name"
        )
        serializer = DashboardTabSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class DashboardTabAssignUserView(APIView):
    """Assign or unassign a dashboard tab to a user (superuser only).

    POST payload: { "tab_slug": "slug", "user_id": 5, "assign": true }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)

        tab_slug = request.data.get("tab_slug")
        user_id = request.data.get("user_id")
        assign = bool(request.data.get("assign", False))

        logger.info(f"Tab assignment request: tab_slug={tab_slug}, user_id={user_id}, assign={assign}")

        if not tab_slug or not user_id:
            return Response(
                {"error": "tab_slug and user_id required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tab = DashboardTab.objects.prefetch_related("users").get(slug=tab_slug)
        except DashboardTab.DoesNotExist:
            logger.warning(f"Tab with slug '{tab_slug}' not found")
            return Response(
                {"error": f"Tab with slug '{tab_slug}' not found. Please create it first."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Resolve user by Django auth id or by custom UserModel id -> username
        user = None
        try:
            user = User.objects.get(id=user_id)
            logger.info(f"Found user by Django auth id: {user.username}")
        except (User.DoesNotExist, ValueError, TypeError) as e:
            logger.info(f"User not found by Django auth id {user_id}, trying UserModel: {e}")
            try:
                profile = UserModel.objects.get(id=user_id)
                user = User.objects.filter(username=profile.username).first()
                if user:
                    logger.info(f"Found user via UserModel: {user.username}")
                else:
                    logger.warning(f"UserModel {user_id} ({profile.username}) has no matching Django User")
            except (UserModel.DoesNotExist, ValueError, TypeError) as e2:
                logger.warning(f"UserModel not found for id {user_id}: {e2}")
                user = None

        if not user:
            logger.error(f"Could not resolve user for id {user_id}")
            return Response(
                {"error": f"User with id {user_id} not found. Please ensure the user has a matching Django auth account."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            if assign:
                tab.users.add(user)
            else:
                tab.users.remove(user)
        except Exception as e:
            logger.error(f"Error updating tab-user relationship: {e}")
            return Response(
                {"error": f"Failed to update tab assignment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"success": True})


class DashboardTabDetailView(APIView):
    """Retrieve, update or delete a DashboardTab by slug (superuser only)."""

    permission_classes = [IsAuthenticated]

    def get_object(self, slug):
        try:
            return DashboardTab.objects.get(slug=slug)
        except DashboardTab.DoesNotExist:
            return None

    def get(self, request, slug=None):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)
        obj = self.get_object(slug)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = DashboardTabSerializer(obj, context={"request": request})
        return Response(serializer.data)

    def put(self, request, slug=None):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)
        obj = self.get_object(slug)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)

        data = request.data or {}
        name = data.get("name")
        description = data.get("description")
        order = data.get("order")
        is_active = data.get("is_active")

        if name is not None:
            obj.name = name
        if description is not None:
            obj.description = description
        if order is not None:
            try:
                obj.order = int(order)
            except Exception:
                pass
        if is_active is not None:
            obj.is_active = bool(is_active)

        obj.save()
        return Response(DashboardTabSerializer(obj, context={"request": request}).data)

    def delete(self, request, slug=None):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)
        obj = self.get_object(slug)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardTabAssignRoleView(APIView):
    """Assign or unassign a dashboard tab to all users with a given role (superuser only).

    POST payload: { tab_slug: "slug", role: "admin", assign: true }
    Supported roles: 'admin'
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)

        tab_slug = request.data.get("tab_slug")
        role = request.data.get("role")
        assign = bool(request.data.get("assign", False))

        if not tab_slug or not role:
            return Response(
                {"error": "tab_slug and role required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if role != "admin":
            return Response(
                {"error": "unsupported role"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            tab = DashboardTab.objects.get(slug=tab_slug)
        except DashboardTab.DoesNotExist:
            return Response(
                {"error": "tab not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Find all UserModel with role='admin' and map to Django auth users
        admins = UserModel.objects.filter(role="admin")
        changed = 0
        errors = []
        for profile in admins:
            try:
                auth_user = User.objects.filter(username=profile.username).first()
                if not auth_user:
                    logger.warning(f"Admin profile {profile.id} ({profile.username}) has no matching Django User")
                    continue
                if assign:
                    if not tab.users.filter(id=auth_user.id).exists():
                        tab.users.add(auth_user)
                        changed += 1
                else:
                    if tab.users.filter(id=auth_user.id).exists():
                        tab.users.remove(auth_user)
                        changed += 1
            except Exception as e:
                logger.error(f"Error processing admin {profile.id}: {e}")
                errors.append(str(profile.id))

        tab.save()
        response_data = {"success": True, "changed": changed}
        if errors:
            response_data["warnings"] = f"Errors processing {len(errors)} admin(s)"
        return Response(response_data)


class DashboardTabsSyncView(APIView):
    """Sync a list of dashboard tabs (create missing, update existing). Superuser only.

    POST body: { "tabs": [ {"name": "Users", "slug": "users", "description": "...", "order": 1}, ... ] }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not getattr(request.user, "is_superuser", False):
            return Response(status=status.HTTP_403_FORBIDDEN)

        payload = request.data or {}
        tabs = payload.get("tabs") or []
        if not isinstance(tabs, list):
            return Response(
                {"error": "tabs must be a list"}, status=status.HTTP_400_BAD_REQUEST
            )

        created = 0
        updated = 0
        for item in tabs:
            slug = (item.get("slug") or "").strip()
            if not slug:
                continue
            name = item.get("name") or slug
            description = item.get("description") or ""
            order = item.get("order") or 0

            obj, was_created = DashboardTab.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "description": description,
                    "order": order,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return Response({"created": created, "updated": updated})


# Tracking views


class RequestOTPView(APIView):
    """Send a one-time password to user's email for login."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"].strip()

        # Find user by email (preferred) or username in custom user table
        user_profile = (
            UserModel.objects.filter(email__iexact=identifier).first()
            or UserModel.objects.filter(username__iexact=identifier).first()
        )
        if not user_profile:
            return Response(
                {"detail": "No account found for the provided identifier."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Basic rate limiting: 1 OTP per 60 seconds
        one_minute_ago = timezone.now() - timezone.timedelta(seconds=60)
        recent = LoginOTP.objects.filter(
            user=user_profile, created_at__gte=one_minute_ago, is_used=False
        ).first()
        if recent:
            return Response(
                {"detail": "Please wait a minute before requesting a new code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Generate 6-digit code
        import random

        code = f"{random.randint(0, 999999):06d}"
        expires = timezone.now() + timezone.timedelta(minutes=5)
        LoginOTP.objects.create(
            user=user_profile,
            email=user_profile.email,
            code_hash=make_password(code),
            expires_at=expires,
        )

        # Send via email
        try:
            from .email_utils import send_login_otp_email

            send_login_otp_email(user_profile, code)
        except Exception:
            # Do not reveal internal errors
            pass

        return Response(
            {"message": "OTP code sent to your email if the account exists."},
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    """Verify OTP and return JWT tokens on success."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"].strip()
        submitted_raw = serializer.validated_data["code"].strip()
        # Normalize: remove any non-digit characters (in case user pasted spaced code)
        import re

        submitted = re.sub(r"\D", "", submitted_raw)

        user_profile = (
            UserModel.objects.filter(email__iexact=identifier).first()
            or UserModel.objects.filter(username__iexact=identifier).first()
        )
        if not user_profile:
            return Response(
                {"detail": "Invalid code or identifier."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check last few active OTPs to avoid race with multiple requests/emails
        now = timezone.now()
        candidates = LoginOTP.objects.filter(
            user=user_profile, is_used=False, expires_at__gte=now
        ).order_by("-created_at")[:5]
        if not candidates:
            return Response(
                {"detail": "No active code found. Please request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        matched = None
        for cand in candidates:
            if check_password(submitted, cand.code_hash):
                matched = cand
                break

        if matched:
            matched.is_used = True
            matched.attempts += 1
            matched.save(update_fields=["is_used", "attempts"])
        else:
            latest = candidates[0]
            latest.attempts += 1
            latest.save(update_fields=["attempts"])
            if latest.attempts >= 5:
                return Response(
                    {"detail": "Too many attempts. Please request a new code."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"detail": "Invalid code. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Ensure a Django auth user exists for JWT
        auth_user = User.objects.filter(username=user_profile.username).first()
        if not auth_user:
            auth_user = User.objects.create_user(
                username=user_profile.username,
                email=user_profile.email,
                password=User.objects.make_random_password(),
            )

        # Issue JWT tokens
        refresh = RefreshToken.for_user(auth_user)
        access = str(refresh.access_token)

        return Response(
            {
                "access": access,
                "refresh": str(refresh),
                "username": user_profile.username,
                "email": user_profile.email,
            },
            status=status.HTTP_200_OK,
        )


class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"].strip()

        user_profile = (
            UserModel.objects.filter(email__iexact=identifier).first()
            or UserModel.objects.filter(username__iexact=identifier).first()
        )
        if not user_profile:
            return Response(
                {"detail": "If the account exists, a code will be sent."},
                status=status.HTTP_200_OK,
            )

        # Rate limit: 1 per 60s
        one_minute_ago = timezone.now() - timezone.timedelta(seconds=60)
        if PasswordResetOTP.objects.filter(
            user=user_profile, created_at__gte=one_minute_ago, is_used=False
        ).exists():
            return Response(
                {"detail": "Please wait a minute before requesting a new code."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        import random

        code = f"{random.randint(0, 999999):06d}"
        expires = timezone.now() + timezone.timedelta(minutes=10)
        PasswordResetOTP.objects.create(
            user=user_profile,
            email=user_profile.email,
            code_hash=make_password(code),
            expires_at=expires,
        )

        try:
            from .email_utils import send_password_reset_otp_email

            send_password_reset_otp_email(user_profile, code)
        except Exception:
            pass

        return Response(
            {"message": "If the account exists, a reset code has been sent."},
            status=status.HTTP_200_OK,
        )


class VerifyPasswordResetView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data["identifier"].strip()
        submitted_raw = serializer.validated_data["code"].strip()
        import re

        submitted = re.sub(r"\D", "", submitted_raw)
        new_password = serializer.validated_data["new_password"]

        user_profile = (
            UserModel.objects.filter(email__iexact=identifier).first()
            or UserModel.objects.filter(username__iexact=identifier).first()
        )
        if not user_profile:
            return Response(
                {"detail": "Invalid code or identifier."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        candidates = PasswordResetOTP.objects.filter(
            user=user_profile, is_used=False, expires_at__gte=now
        ).order_by("-created_at")[:5]
        if not candidates:
            return Response(
                {"detail": "No active code found. Please request a new code."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        matched = None
        for cand in candidates:
            if check_password(submitted, cand.code_hash):
                matched = cand
                break

        if matched:
            matched.is_used = True
            matched.attempts += 1
            matched.save(update_fields=["is_used", "attempts"])
        else:
            latest = candidates[0]
            latest.attempts += 1
            latest.save(update_fields=["attempts"])
            if latest.attempts >= 5:
                return Response(
                    {"detail": "Too many attempts. Please request a new code."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"detail": "Invalid code. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update passwords in both models
        user_profile.password = make_password(new_password)
        user_profile.login_attempts = 0  # optional reset
        user_profile.save(update_fields=["password", "login_attempts"])

        auth_user = User.objects.filter(username=user_profile.username).first()
        if auth_user:
            auth_user.set_password(new_password)
            auth_user.save(update_fields=["password"])
        else:
            # Create auth user if missing (edge case)
            User.objects.create_user(
                username=user_profile.username,
                email=user_profile.email,
                password=new_password,
            )

        return Response(
            {"message": "Password reset successful. You can now log in."},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    """Allow an authenticated user to change their password by providing the current password.

    POST body:
    - current_password
    - new_password
    - confirm_password

    Updates both the custom UserModel and the Django auth user password.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = (request.data.get("current_password") or "").strip()
        new_password = (request.data.get("new_password") or "").strip()
        confirm_password = (request.data.get("confirm_password") or "").strip()

        if not current_password or not new_password or not confirm_password:
            return Response(
                {
                    "detail": "current_password, new_password and confirm_password are required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_password != confirm_password:
            return Response(
                {"confirm_password": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 6:
            return Response(
                {"new_password": "Password must be at least 6 characters long."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user_profile = UserModel.objects.get(username=request.user.username)
        except UserModel.DoesNotExist:
            return Response(
                {"detail": "User profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify current password against our custom user model hash
        if not check_password(current_password, user_profile.password):
            return Response(
                {"current_password": "Current password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update password in both models
        user_profile.password = make_password(new_password)
        user_profile.login_attempts = 0
        user_profile.save(update_fields=["password", "login_attempts"])

        auth_user = User.objects.filter(username=user_profile.username).first()
        if auth_user:
            auth_user.set_password(new_password)
            auth_user.save(update_fields=["password"])
        else:
            # Create auth user if missing (edge case)
            User.objects.create_user(
                username=user_profile.username,
                email=user_profile.email,
                password=new_password,
            )

        return Response(
            {"message": "Password updated successfully."},
            status=status.HTTP_200_OK,
        )


class TrackingListCreateView(generics.ListCreateAPIView):
    """List all trackings or create a new tracking record.

    Non-admins see only their own trackings. Admins see all.

    IMPORTANT: If tracking_number already exists, this will UPDATE it
    instead of rejecting with a validation error. This allows both
    user and admin to add the same tracking number, and ownership
    will be synced automatically.
    """

    queryset = Tracking.objects.all()
    serializer_class = TrackingSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        # Determine if requester is admin via Django user or our profile role
        django_user = getattr(self.request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        if is_admin:
            return qs
        # Filter to records owned by this user profile
        try:
            profile = UserModel.objects.get(username=django_user.username)
            return qs.filter(owner=profile)
        except UserModel.DoesNotExist:
            return qs.none()

    def create(self, request, *args, **kwargs):
        """
        Override create to handle duplicate tracking_numbers gracefully.
        If tracking already exists, UPDATE it instead of returning validation error.
        """
        tracking_number = request.data.get("tracking_number")

        # Check if tracking already exists
        existing = None
        if tracking_number:
            try:
                existing = Tracking.objects.get(tracking_number=tracking_number)
            except Tracking.DoesNotExist:
                pass

        if existing:
            # UPDATE existing tracking instead of creating new
            serializer = self.get_serializer(existing, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update_tracking(serializer, existing)

            # Refresh serializer to get updated data after sync
            existing.refresh_from_db()
            serializer = self.get_serializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # CREATE new tracking
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

            # Refresh to get synced data
            tracking_number = serializer.instance.tracking_number
            tracking = Tracking.objects.get(tracking_number=tracking_number)
            serializer = self.get_serializer(tracking)

            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

    def perform_update_tracking(self, serializer, existing):
        """Update existing tracking and sync ownership."""
        request_user = getattr(self.request, "user", None)

        # Determine if requester is admin
        is_admin = bool(
            getattr(request_user, "is_staff", False)
            or getattr(request_user, "is_superuser", False)
        )
        if (
            not is_admin
            and request_user
            and getattr(request_user, "is_authenticated", False)
        ):
            try:
                req_profile = UserModel.objects.get(username=request_user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False

        # If non-admin user, force ownership to them
        if (
            not is_admin
            and request_user
            and getattr(request_user, "is_authenticated", False)
        ):
            try:
                owner_profile = UserModel.objects.get(username=request_user.username)
                serializer.save(owner=owner_profile)
            except UserModel.DoesNotExist:
                serializer.save()
        else:
            serializer.save()

        # Sync after update
        existing.refresh_from_db()
        existing.sync_duplicates()

    def perform_create(self, serializer):
        """
        Enforce ownership rules on create (called by parent's create() for NEW trackings only):
        - Admins: MUST specify an owner and it cannot be an admin account
        - Non-admins: Owner is forced to the authenticated user (ignore provided owner)
        - After save, sync ownership
        """
        request_user = getattr(self.request, "user", None)

        # Determine if requester is admin (Django flags or our profile role)
        is_admin = bool(
            getattr(request_user, "is_staff", False)
            or getattr(request_user, "is_superuser", False)
        )
        if (
            not is_admin
            and request_user
            and getattr(request_user, "is_authenticated", False)
        ):
            try:
                req_profile = UserModel.objects.get(username=request_user.username)
                is_admin = req_profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False

        if is_admin:
            owner = serializer.validated_data.get("owner")
            # If admin specified an owner, validate it's not an admin account
            if owner and getattr(owner, "role", None) == "admin":
                raise ValidationError(
                    {
                        "owner": "Owner cannot be an admin user. Please select a customer."
                    }
                )
            tracking = serializer.save()
            tracking.sync_duplicates()
            return

        # Non-admin user: force ownership to current user profile
        if request_user and getattr(request_user, "is_authenticated", False):
            try:
                owner_profile = UserModel.objects.get(username=request_user.username)
            except UserModel.DoesNotExist:
                raise ValidationError(
                    {
                        "owner": "User profile not found. Please ensure your account is set up."
                    }
                )
            tracking = serializer.save(owner=owner_profile)
            tracking.sync_duplicates()
            return

        raise ValidationError({"detail": "Authentication required."})


class TrackingDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a single tracking by numeric ID."""

    queryset = Tracking.objects.all()
    serializer_class = TrackingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "pk"

    def perform_update(self, serializer):
        """
        Prevent assigning an admin user as the owner on updates.
        """
        new_owner = serializer.validated_data.get("owner")
        if new_owner and getattr(new_owner, "role", None) == "admin":
            raise ValidationError(
                {"owner": "Owner cannot be an admin user. Please select a customer."}
            )
        tracking = serializer.save()
        # Sync duplicates after update
        tracking.sync_duplicates()


class TrackingRetrieveByNumberView(generics.RetrieveAPIView):
    """Retrieve a single tracking by its unique tracking_number.

    Public access is allowed so end-users can check their package status
    without requiring authentication.
    """

    queryset = Tracking.objects.all()
    serializer_class = TrackingSerializer
    permission_classes = [AllowAny]
    lookup_field = "tracking_number"


class ShippingMarkListView(generics.ListAPIView):
    """List shipping marks with optional search by mark_id or owner name.
    Intended for admin selection when adding a tracking.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ShippingMarkSerializer

    class _Paginator(PageNumberPagination):
        page_size = 20
        page_size_query_param = "page_size"
        max_page_size = 100

    pagination_class = _Paginator

    def get_queryset(self):
        qs = ShippingMark.objects.select_related("owner").all().order_by("-created_at")
        q = self.request.query_params.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(mark_id__icontains=q)
                | Q(name__icontains=q)
                | Q(owner__username__icontains=q)
                | Q(owner__full_name__icontains=q)
            )
        return qs


class InvoicePreviewView(APIView):
    """Preview invoice data for a given shipping mark and container.

    Query params:
    - mark_id: required (ShippingMark.mark_id)
    - container_id: required (Container.id)

    Response:
    {
      owner: { id, username, full_name, email },
      mark_id: str,
      container: { id, container_number, status },
      items: [ { id, tracking_number, status, cbm, shipping_fee, goods_type } ],
      totals: { count, total_cbm, total_fee }
    }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Admin check (support either Django is_staff or our UserModel.role)
        django_user = getattr(request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if (
            not is_admin
            and django_user
            and getattr(django_user, "is_authenticated", False)
        ):
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        if not is_admin:
            raise PermissionDenied("Admin access required")

        mark_id = (request.query_params.get("mark_id") or "").strip()
        container_id = request.query_params.get("container_id")
        if not mark_id or not container_id:
            return Response(
                {"detail": "mark_id and container_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve mark and owner
        try:
            sm = ShippingMark.objects.select_related("owner").get(mark_id=mark_id)
        except ShippingMark.DoesNotExist:
            return Response({"detail": "Shipping mark not found"}, status=404)

        # Resolve container
        try:
            container = Container.objects.get(id=container_id)
        except Container.DoesNotExist:
            return Response({"detail": "Container not found"}, status=404)

        # Fetch items (trackings)
        qs = Tracking.objects.filter(
            shipping_mark=mark_id, container_id=container.id
        ).order_by("-date_added")

        items = [
            {
                "id": t.id,
                "tracking_number": t.tracking_number,
                "status": t.status,
                "cbm": float(t.cbm or 0),
                "shipping_fee": float(t.shipping_fee or 0),
                "goods_type": t.goods_type,
            }
            for t in qs
        ]

        agg = qs.aggregate(total_cbm=Sum("cbm"), total_fee=Sum("shipping_fee"))
        total_cbm = float(agg.get("total_cbm") or 0)
        total_fee = float(agg.get("total_fee") or 0)

        # Compute exchange rate and GHS total for email and invoice
        from .models import CurrencyRate

        exchange_rate = CurrencyRate.get_current_rate()
        try:
            total_amount_ghs = float(total_fee) * float(exchange_rate)
        except Exception:
            total_amount_ghs = 0.0

        data = {
            "owner": {
                "id": sm.owner.id if sm.owner else None,
                "username": sm.owner.username if sm.owner else None,
                "full_name": sm.owner.full_name if sm.owner else None,
                "email": sm.owner.email if sm.owner else None,
            },
            "items": items,
            "totals": {
                "count": len(items),
                "total_cbm": total_cbm,
                "total_fee": total_fee,
            },
        }
        return Response(data, status=200)


class InvoiceSendView(APIView):
    """Send an invoice email to the owner for a given mark and container.

    POST body: { mark_id: str, container_id: number }
    Returns: { notification_id, sent: true }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Admin check
        django_user = getattr(request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if (
            not is_admin
            and django_user
            and getattr(django_user, "is_authenticated", False)
        ):
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        if not is_admin:
            raise PermissionDenied("Admin access required")

        mark_id = (request.data.get("mark_id") or "").strip()
        container_id = request.data.get("container_id")
        if not mark_id or not container_id:
            return Response(
                {"detail": "mark_id and container_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sm = ShippingMark.objects.select_related("owner").get(mark_id=mark_id)
        except ShippingMark.DoesNotExist:
            return Response({"detail": "Shipping mark not found"}, status=404)
        if not sm.owner:
            return Response({"detail": "Shipping mark has no owner"}, status=400)

        try:
            container = Container.objects.get(id=container_id)
        except Container.DoesNotExist:
            return Response({"detail": "Container not found"}, status=404)

        qs = Tracking.objects.filter(
            shipping_mark=mark_id, container_id=container.id
        ).order_by("-date_added")
        items = list(qs)
        if not items:
            return Response(
                {"detail": "No items found for this mark in the selected container"},
                status=400,
            )

        agg = qs.aggregate(total_cbm=Sum("cbm"), total_fee=Sum("shipping_fee"))
        total_cbm = float(agg.get("total_cbm") or 0)
        total_fee = float(agg.get("total_fee") or 0)

        # Compute exchange rate and GHS total for email and invoice
        from .models import CurrencyRate

        exchange_rate = CurrencyRate.get_current_rate()
        try:
            total_amount_ghs = float(total_fee) * float(exchange_rate)
        except Exception:
            total_amount_ghs = 0.0

        # Build email
        from django.conf import settings
        from .email_utils import send_notification_email

        subject = (
            f"Invoice for Container {container.container_number} - Mark {sm.mark_id}"
        )

        # Plain text
        lines = [
            f"Hello {sm.owner.full_name},",
            "",
            f"Here is your invoice summary for container {container.container_number}.",
            f"Shipping Mark: {sm.mark_id}",
            "",
            "Items:",
        ]
        for t in items:
            lines.append(
                f"- {t.tracking_number} | Status: {t.status} | CBM: {t.cbm or 0} | Fee: ${t.shipping_fee or 0}"
            )
        lines += [
            "",
            f"Total items: {len(items)}",
            f"Total CBM: {total_cbm:.3f}",
            f"Total Fee (USD): ${total_fee:.2f}",
            f"Total Fee (GHS): GH₵{total_amount_ghs:.2f}",
            f"Exchange Rate: 1 USD = {exchange_rate} GHS",
            "",
            f"You can review your shipments at {getattr(settings, 'SITE_URL', '')}/tracking",
            "Thank you!",
        ]
        message = "\n".join(lines)

        # HTML version
        rows = "".join(
            [
                f"<tr><td style='padding:6px;border:1px solid #e5e7eb'>{t.tracking_number}</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb'>{t.status}</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;text-align:right'>{(t.cbm or 0):.3f}</td>"
                f"<td style='padding:6px;border:1px solid #e5e7eb;text-align:right'>${(t.shipping_fee or 0):.2f}</td></tr>"
                for t in items
            ]
        )

        # Embed logo as base64 for email reliability
        import base64
        import os
        logo_base64 = ""
        logo_path = os.path.join(os.path.dirname(__file__), "static", "fofoofo.png")
        if os.path.exists(logo_path):
            try:
                with open(logo_path, "rb") as img_file:
                    logo_data = base64.b64encode(img_file.read()).decode("utf-8")
                    logo_base64 = f"data:image/png;base64,{logo_data}"
            except Exception as e:
                logger.warning(f"Could not embed logo in email: {e}")

        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
          <div style="max-width: 700px; margin: 0 auto;">
            {f'<div style="text-align: center; margin-bottom: 20px; padding: 20px 0; border-bottom: 2px solid #e5e7eb;"><img src="{logo_base64}" alt="Fofoo Logo" style="max-width: 200px; height: auto; object-fit: contain; display: block; margin: 0 auto;"></div>' if logo_base64 else ''}
            <h2 style="color:#2563eb;">Invoice Summary</h2>
            <p>Hello <strong>{sm.owner.full_name}</strong>,</p>
            <p>Here is your invoice summary for container <strong>{container.container_number}</strong>.</p>
            <p><strong>Shipping Mark:</strong> {sm.mark_id}</p>
            <table style="border-collapse:collapse; width:100%; background:#fff">
              <thead>
                <tr style="background:#f3f4f6;">
                  <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Tracking #</th>
                  <th style="padding:8px;border:1px solid #e5e7eb;text-align:left">Status</th>
                  <th style="padding:8px;border:1px solid #e5e7eb;text-align:right">CBM</th>
                  <th style="padding:8px;border:1px solid #e5e7eb;text-align:right">Fee</th>
                </tr>
              </thead>
              <tbody>
                {rows}
              </tbody>
              <tfoot>
                <tr style="background:#f3f4f6;">
                  <td colspan="2" style="padding:8px;border:1px solid #e5e7eb;text-align:right"><strong>Totals</strong></td>
                  <td style="padding:8px;border:1px solid #e5e7eb;text-align:right"><strong>{total_cbm:.3f}</strong></td>
                                    <td style="padding:8px;border:1px solid #e5e7eb;text-align:right"><strong>${total_fee:.2f} USD</strong></td>
                                </tr>
                                <tr style="background:#f0fdf4;">
                                    <td colspan="3" style="padding:8px;border:1px solid #e5e7eb;text-align:right"><strong>Total (GHS):</strong></td>
                                    <td style="padding:8px;border:1px solid #e5e7eb;text-align:right;color:#15803d;"><strong>GH₵{total_amount_ghs:.2f}</strong></td>
                                </tr>
                                <tr>
                                    <td colspan="4" style="padding:8px;border:1px solid #e5e7eb;text-align:right;font-style:italic;color:#6b7280;font-size:12px;">Exchange Rate: 1 USD = {exchange_rate} GHS</td>
                </tr>
              </tfoot>
            </table>
            <p style="margin-top:16px;">For Payment Details contact <strong>0540266839</strong> .</p>
            <p style="margin-top:16px;">Thank you for shipping with us.</p>
          </div>
        </body>
        </html>
        """

        # Create invoice record in database
        from datetime import datetime, timedelta

        # Generate unique invoice number
        today = datetime.now().strftime("%Y%m%d")
        base = f"INV-{today}-"
        existing = Invoice.objects.filter(invoice_number__startswith=base).order_by(
            "invoice_number"
        )
        seq = len(existing) + 1
        invoice_number = f"{base}{seq:03d}"

        # Get UserModel instance for created_by
        created_by_user = None
        django_user = getattr(request, "user", None)
        if django_user and getattr(django_user, "is_authenticated", False):
            try:
                created_by_user = UserModel.objects.get(username=django_user.username)
            except UserModel.DoesNotExist:
                pass

        # Create invoice
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            shipping_mark=mark_id,
            customer_name=sm.owner.full_name if sm.owner else "",
            customer_email=sm.owner.email if sm.owner else "",
            subtotal=total_fee,
            tax_amount=0,
            discount_amount=0,
            total_amount=total_fee,
            exchange_rate=exchange_rate,
            total_amount_ghs=total_amount_ghs,
            status="pending",
            issue_date=datetime.now().date(),
            due_date=(datetime.now() + timedelta(days=30)).date(),
            container=container,
            created_by=created_by_user,
        )

        # Create invoice items
        bulk_items = []
        for t in items:
            bulk_items.append(
                InvoiceItem(
                    invoice=invoice,
                    tracking=t,
                    description=f"Freight for {t.tracking_number}",
                    tracking_number=t.tracking_number,
                    cbm=t.cbm or 0,
                    rate_per_cbm=0,
                    goods_type=t.goods_type or "",
                    total_amount=t.shipping_fee or 0,
                )
            )
        InvoiceItem.objects.bulk_create(bulk_items)

        # Generate PDF invoice
        pdf_content = None
        pdf_filename = None
        try:
            # Check if reportlab is available
            try:
                import reportlab
            except ImportError:
                logger.warning("reportlab is not installed. PDF generation will be skipped. Install with: pip install reportlab")
                raise
            
            from .pdf_utils import generate_invoice_pdf
            # Refresh invoice to get items
            invoice.refresh_from_db()
            invoice_items = list(invoice.items.all())
            pdf_content = generate_invoice_pdf(
                invoice=invoice,
                invoice_items=invoice_items,
                container=container,
                shipping_mark=sm,
                owner=sm.owner
            )
            pdf_filename = f"Invoice_{invoice.invoice_number}.pdf"
        except ImportError as e:
            logger.warning(f"Could not import PDF generation module: {e}. PDF attachment will be skipped.")
        except Exception as e:
            logger.warning(f"Could not generate PDF invoice: {e}. PDF attachment will be skipped.")
            # Continue without PDF attachment

        # Send email notification
        notif = send_notification_email(
            user=sm.owner,
            notification_type="invoice_ready",
            subject=subject,
            message=message,
            html_message=html_message,
            tracking=None,
            pdf_attachment=pdf_content,
            pdf_filename=pdf_filename,
        )

        return Response(
            {
                "notification_id": notif.id,
                "sent": notif.status == "sent",
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
            },
            status=200,
        )


class InvoiceListCreateView(generics.ListCreateAPIView):
    """Admin list/create invoices with filtering and ordering.

    GET query params:
    - page, page_size
    - search: matches invoice_number, shipping_mark, container.container_number
    - status: exact status
    - container_id: exact container id
    - ordering: one of -created_at, created_at, -due_date, due_date, -total_amount, total_amount

    POST body supports two modes:
    A) Auto-generate from mark+container:
       { mark_id, container_id, invoice_number?, issue_date?, due_date?, tax_amount?, discount_amount?, notes? }
       Creates Invoice + InvoiceItems from trackings (shipping_fee as line totals).

    B) Direct create (advanced): provide required fields and totals yourself.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer

    class _Paginator(PageNumberPagination):
        page_size = 20
        page_size_query_param = "page_size"
        max_page_size = 100

    pagination_class = _Paginator

    def _is_admin(self, user):
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin and getattr(user, "is_authenticated", False):
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        return is_admin

    def get_queryset(self):
        if not self._is_admin(self.request.user):
            raise PermissionDenied("Admin access required")
        qs = Invoice.objects.select_related("container", "created_by").all()
        params = self.request.query_params
        search = (params.get("search") or "").strip()
        status_val = (params.get("status") or "").strip()
        container_id = params.get("container_id")
        if search:
            qs = qs.filter(
                Q(invoice_number__icontains=search)
                | Q(shipping_mark__icontains=search)
                | Q(container__container_number__icontains=search)
            )
        if status_val:
            qs = qs.filter(status=status_val)
        if container_id:
            qs = qs.filter(container_id=container_id)
        ordering = params.get("ordering") or "-created_at"
        allowed = {
            "created_at",
            "-created_at",
            "due_date",
            "-due_date",
            "total_amount",
            "-total_amount",
        }
        if ordering not in allowed:
            ordering = "-created_at"
        return qs.order_by(ordering)

    def perform_create(self, serializer):
        # Only admins can create
        if not self._is_admin(self.request.user):
            raise PermissionDenied("Admin access required")

        data = self.request.data
        mark_id = (data.get("mark_id") or "").strip()
        container_id = data.get("container_id")

        if mark_id and container_id:
            # Mode A: auto-generate from trackings within mark+container
            try:
                container = Container.objects.get(id=container_id)
            except Container.DoesNotExist:
                raise ValidationError({"container_id": "Container not found"})

            # Fetch trackings
            tqs = Tracking.objects.filter(
                shipping_mark=mark_id, container_id=container.id
            ).order_by("-date_added")
            items = list(tqs)
            if not items:
                raise ValidationError(
                    "No items found for this mark in the selected container"
                )

            # Compute totals
            agg = tqs.aggregate(total_fee=Sum("shipping_fee"))
            subtotal = float(agg.get("total_fee") or 0)
            tax_amount = float(data.get("tax_amount") or 0)
            discount_amount = float(data.get("discount_amount") or 0)
            total_amount = subtotal + tax_amount - discount_amount

            # Generate invoice number if missing
            invoice_number = (data.get("invoice_number") or "").strip()
            if not invoice_number:
                from datetime import datetime

                today = datetime.now().strftime("%Y%m%d")
                base = f"INV-{today}-"
                # Find next sequence for today
                existing = Invoice.objects.filter(
                    invoice_number__startswith=base
                ).order_by("invoice_number")
                seq = len(existing) + 1
                invoice_number = f"{base}{seq:03d}"

            inv = Invoice.objects.create(
                invoice_number=invoice_number,
                shipping_mark=mark_id,
                customer_name=data.get("customer_name", ""),
                customer_email=data.get("customer_email", ""),
                subtotal=subtotal,
                tax_amount=tax_amount,
                discount_amount=discount_amount,
                total_amount=total_amount,
                status=data.get("status") or "pending",
                issue_date=data.get("issue_date") or None,
                due_date=data.get("due_date") or None,
                paid_date=data.get("paid_date") or None,
                payment_method=data.get("payment_method", ""),
                payment_reference=data.get("payment_reference", ""),
                notes=data.get("notes", ""),
                container=container,
                created_by=getattr(self.request, "user", None),
            )

            # Create items
            bulk_items = []
            for t in items:
                bulk_items.append(
                    InvoiceItem(
                        invoice=inv,
                        tracking=t,
                        description=f"Freight for {t.tracking_number}",
                        tracking_number=t.tracking_number,
                        cbm=t.cbm or 0,
                        rate_per_cbm=0,  # Unknown at this point; can be backfilled
                        goods_type=t.goods_type or "",
                        total_amount=t.shipping_fee or 0,
                    )
                )
            InvoiceItem.objects.bulk_create(bulk_items)

            # Expose created invoice instance to serializer
            serializer.instance = inv
            return

        # Mode B: default create with provided fields
        serializer.save(created_by=getattr(self.request, "user", None))


class InvoiceDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer
    queryset = Invoice.objects.select_related("container", "created_by").all()

    def _is_admin(self, user):
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin and getattr(user, "is_authenticated", False):
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        return is_admin

    def update(self, request, *args, **kwargs):
        if not self._is_admin(request.user):
            raise PermissionDenied("Admin access required")
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        old_status = instance.status

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Send thank you email if status changed to paid
        new_status = serializer.instance.status
        if old_status != "paid" and new_status == "paid":
            self._send_payment_thank_you_email(serializer.instance)

        return Response(serializer.data)

    def _send_payment_thank_you_email(self, invoice):
        """Send a thank you email when invoice is marked as paid."""
        from buysellapi.email_utils import send_notification_email

        # Get the customer (owner of the shipping mark)
        if not invoice.shipping_mark:
            return

        try:
            customer = UserModel.objects.get(
                shipping_mark__mark_id=invoice.shipping_mark
            )
        except UserModel.DoesNotExist:
            return

        subject = f"Payment Received - Thank You! Invoice #{invoice.invoice_number}"

        # Prepare amount display
        amount_usd = f"${invoice.total_amount}"
        amount_ghs = ""
        exchange_rate_text = ""

        if invoice.exchange_rate and invoice.total_amount_ghs:
            amount_ghs = f" (GH₵{invoice.total_amount_ghs})"
            exchange_rate_text = (
                f"\n- Exchange Rate: 1 USD = {invoice.exchange_rate} GHS"
            )

        # Create plain text message
        message = f"""Dear {customer.full_name or customer.username},

Thank you for your payment!

We are pleased to confirm that we have received your payment for Invoice #{invoice.invoice_number}.

Invoice Details:
- Invoice Number: {invoice.invoice_number}
- Container: {invoice.container.container_number if invoice.container else 'N/A'}
- Shipping Mark: {invoice.shipping_mark}
- Amount Paid: {amount_usd}{amount_ghs}{exchange_rate_text}
- Payment Date: {timezone.now().strftime('%B %d, %Y')}

Your shipment will continue to be processed according to schedule. You can track your shipment status through your account dashboard.

If you have any questions or concerns, please don't hesitate to contact us.

Thank you for your business!

Best regards,
BuySell Shipping Team
"""

        # Create HTML message
        html_message = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">Payment Received ✓</h1>
                </div>
                
                <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 10px 10px;">
                    <p style="font-size: 16px; margin-bottom: 20px;">Dear <strong>{customer.full_name or customer.username}</strong>,</p>
                    
                    <p style="font-size: 16px; margin-bottom: 20px;">Thank you for your payment! We are pleased to confirm that we have received your payment for Invoice <strong>#{invoice.invoice_number}</strong>.</p>
                    
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10b981;">
                        <h3 style="color: #1f2937; margin-top: 0;">Invoice Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280;"><strong>Invoice Number:</strong></td>
                                <td style="padding: 8px 0; text-align: right;">{invoice.invoice_number}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280;"><strong>Container:</strong></td>
                                <td style="padding: 8px 0; text-align: right;">{invoice.container.container_number if invoice.container else 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280;"><strong>Shipping Mark:</strong></td>
                                <td style="padding: 8px 0; text-align: right;">{invoice.shipping_mark}</td>
                            </tr>
                            <tr style="border-top: 2px solid #e5e7eb;">
                                <td style="padding: 12px 0; color: #1f2937; font-size: 18px;"><strong>Amount Paid (USD):</strong></td>
                                <td style="padding: 12px 0; text-align: right; color: #10b981; font-size: 20px; font-weight: bold;">${invoice.total_amount}</td>
                            </tr>
                            {f'''<tr>
                                <td style="padding: 8px 0; color: #6b7280;"><strong>Exchange Rate:</strong></td>
                                <td style="padding: 8px 0; text-align: right; font-style: italic;">1 USD = {invoice.exchange_rate} GHS</td>
                            </tr>
                            <tr style="background: #f0fdf4;">
                                <td style="padding: 12px 0; color: #15803d; font-size: 18px;"><strong>Amount Paid (GHS):</strong></td>
                                <td style="padding: 12px 0; text-align: right; color: #15803d; font-size: 20px; font-weight: bold;">GH₵{invoice.total_amount_ghs}</td>
                            </tr>''' if invoice.exchange_rate and invoice.total_amount_ghs else ''}
                            <tr>
                                <td style="padding: 8px 0; color: #6b7280;"><strong>Payment Date:</strong></td>
                                <td style="padding: 8px 0; text-align: right;">{timezone.now().strftime('%B %d, %Y')}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p style="font-size: 16px; margin: 20px 0;">Your shipment will continue to be processed according to schedule. You can track your shipment status through your account dashboard.</p>
                    
                    <p style="font-size: 16px; margin: 20px 0;">If you have any questions or concerns, please don't hesitate to contact us.</p>
                    
                    <div style="background: #eff6ff; padding: 15px; border-radius: 8px; margin-top: 30px;">
                        <p style="margin: 0; color: #1e40af; font-size: 14px;">
                            <strong>Thank you for your business!</strong><br>
                            BuySell Shipping Team
                        </p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

        try:
            send_notification_email(
                user=customer,
                notification_type="invoice_paid",
                subject=subject,
                message=message,
                html_message=html_message,
            )
        except Exception as e:
            logger.error(
                f"Failed to send payment thank you email for invoice {invoice.id}: {str(e)}"
            )


class EnsureProfileView(APIView):
    """Ensure a UserModel profile exists for the authenticated Django user.

    - GET: returns current profile data if exists, 404 if missing
    - POST: creates a minimal profile if missing, returns 201 or 200 if already exists
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            profile = UserModel.objects.get(username=request.user.username)
            data = UserModelSerializer(profile).data
            return Response(data, status=status.HTTP_200_OK)
        except UserModel.DoesNotExist:
            return Response(
                {"message": "Profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request):
        try:
            profile = UserModel.objects.get(username=request.user.username)
            data = UserModelSerializer(profile).data
            return Response(data, status=status.HTTP_200_OK)
        except UserModel.DoesNotExist:
            # Create a minimal profile using available Django user info
            dj = request.user
            username = (getattr(dj, "username", "user") or "user")[:10]
            base_email = getattr(dj, "email", "") or f"{username}@example.com"
            full_name = getattr(dj, "get_full_name", None)
            if callable(full_name):
                full_name = full_name() or username
            else:
                full_name = username

            # Provide safe defaults for required fields
            from django.contrib.auth.hashers import make_password

            # Ensure unique email if the table enforces uniqueness
            email_candidate = base_email
            if UserModel.objects.filter(email=email_candidate).exists():
                # Attempt a few variants to avoid the unique constraint
                local, _, domain = email_candidate.partition("@")
                if not domain:
                    local, domain = (username, "example.com")
                for i in range(1, 21):
                    candidate = f"{local}+{i}@{domain}"
                    if not UserModel.objects.filter(email=candidate).exists():
                        email_candidate = candidate
                        break

            try:
                profile = UserModel.objects.create(
                    username=username,
                    full_name=full_name[:30],
                    email=email_candidate,
                    password=make_password("autocreated"),
                    contact="N/A",
                    location="N/A",
                    status="active",
                    role="user",
                )
            except IntegrityError as ie:
                # Final fallback: return a conflict with guidance
                return Response(
                    {
                        "message": "Could not auto-create profile due to unique constraints",
                        "detail": str(ie),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            data = UserModelSerializer(profile).data
            return Response(data, status=status.HTTP_201_CREATED)


class MyShippingMarkView(APIView):
    """Get/create/update the current user's permanent shipping mark.

    Methods
    - GET: return the user's shipping mark if it exists
    - POST: create a shipping mark if none exists (name required)
    - PUT: update the name on the user's shipping mark
    """

    permission_classes = [IsAuthenticated]

    def _get_profile(self, request):
        try:
            return UserModel.objects.get(username=request.user.username)
        except UserModel.DoesNotExist:
            return None

    def get(self, request):
        profile = self._get_profile(request)
        if not profile:
            return Response(
                {"message": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            mark = ShippingMark.objects.get(owner=profile)
        except ShippingMark.DoesNotExist:
            return Response(
                {"message": "No shipping mark for this user"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = ShippingMarkSerializer(mark).data
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        profile = self._get_profile(request)
        if not profile:
            return Response(
                {"message": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Enforce single permanent shipping mark per user
        existing = ShippingMark.objects.filter(owner=profile).first()
        if existing:
            data = ShippingMarkSerializer(existing).data
            return Response(
                {"message": "You already have a shipping mark", **data},
                status=status.HTTP_200_OK,
            )

        name = (request.data.get("name") or "").strip()
        if not name:
            return Response(
                {"message": "Name is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Generate a unique mark_id in the format M856-FIMXYZ
        mark_id = self._generate_unique_mark_id()
        mark = ShippingMark.objects.create(owner=profile, mark_id=mark_id, name=name)
        data = ShippingMarkSerializer(mark).data
        return Response(data, status=status.HTTP_201_CREATED)

    def put(self, request):
        profile = self._get_profile(request)
        if not profile:
            return Response(
                {"message": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            mark = ShippingMark.objects.get(owner=profile)
        except ShippingMark.DoesNotExist:
            return Response(
                {"message": "No shipping mark to update"},
                status=status.HTTP_404_NOT_FOUND,
            )

        name = (request.data.get("name") or "").strip()
        if not name:
            return Response(
                {"message": "Name is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Optional: also update user profile name if requested
        update_profile = bool(request.data.get("updateUserProfile", False))

        mark.name = name
        mark.save(update_fields=["name"])

        if update_profile:
            try:
                profile.full_name = name
                profile.save(update_fields=["full_name"])
            except Exception:
                pass

        data = ShippingMarkSerializer(mark).data
        return Response(data, status=status.HTTP_200_OK)

    def delete(self, request):
        # Deletion is not allowed for permanent marks
        return Response(
            {"message": "Shipping mark is permanent and cannot be deleted"},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _generate_unique_mark_id(self) -> str:
        import random

        prefix = "FIM"
        # Try a few times to generate a unique 3-digit code
        for _ in range(20):
            code = random.randint(100, 999)
            candidate = f"{prefix}{code}"
            if not ShippingMark.objects.filter(mark_id=candidate).exists():
                return candidate
        # As a fallback, append a random 6-digit number
        while True:
            code = random.randint(100000, 999999)
            candidate = f"{prefix}{code}"
            if not ShippingMark.objects.filter(mark_id=candidate).exists():
                return candidate


class AdminShippingMarksListView(APIView):
    """Admin view to list all shipping marks with pagination and search"""

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        """Check if user is admin"""
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def get(self, request):
        """List all shipping marks with pagination, sorting, and search"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get query parameters
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 20))
        sort_field = request.query_params.get("sortField", "created_at")
        sort_direction = request.query_params.get("sortDirection", "desc")
        search = request.query_params.get("search", "")

        # Map frontend field names to model fields
        field_mapping = {
            "markId": "mark_id",
            "name": "name",
            "createdAt": "created_at",
        }
        db_sort_field = field_mapping.get(sort_field, "created_at")

        # Build queryset
        queryset = ShippingMark.objects.select_related("owner").all()

        # Apply search filter
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(mark_id__icontains=search)
                | Q(name__icontains=search)
                | Q(owner__username__icontains=search)
                | Q(owner__full_name__icontains=search)
            )

        # Apply sorting
        if sort_direction == "desc":
            queryset = queryset.order_by(f"-{db_sort_field}")
        else:
            queryset = queryset.order_by(db_sort_field)

        # Get total count
        total = queryset.count()

        # Apply pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_data = queryset[start:end]

        # Serialize with owner information
        marks_data = []
        for mark in paginated_data:
            marks_data.append(
                {
                    "id": mark.id,
                    "mark_id": mark.mark_id,
                    "name": mark.name,
                    "created_at": mark.created_at.isoformat(),
                    "owner": {
                        "id": mark.owner.id,
                        "username": mark.owner.username,
                        "full_name": mark.owner.full_name,
                        "email": mark.owner.email,
                    },
                }
            )

        return Response(
            {
                "data": marks_data,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": (total + limit - 1) // limit,
            },
            status=status.HTTP_200_OK,
        )


# Container Management Views
class AdminContainerListView(APIView):
    """Admin view for listing and creating containers."""

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        """Check if user has admin privileges."""
        return (
            user.is_staff
            or user.is_superuser
            or (hasattr(user, "role") and user.role == "admin")
        )

    def get(self, request):
        """Get list of all containers with pagination, search, and sorting."""
        # Check admin permission
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin authentication required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            # Get query parameters
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            search = request.GET.get("search", "").strip()
            sort_by = request.GET.get("sortBy", "-created_at")

            # Build query
            queryset = Container.objects.all()

            # Apply search filter
            if search:
                queryset = queryset.filter(
                    Q(container_number__icontains=search)
                    | Q(port_of_loading__icontains=search)
                    | Q(port_of_discharge__icontains=search)
                    | Q(status__icontains=search)
                )

            # Apply sorting
            if sort_by:
                queryset = queryset.order_by(sort_by)

            # Get total count
            total = queryset.count()

            # Apply pagination
            start = (page - 1) * limit
            end = start + limit
            containers = queryset[start:end]

            # Import serializer
            from .serializers import ContainerSerializer

            serializer = ContainerSerializer(containers, many=True)

            return Response(
                {
                    "data": serializer.data,
                    "total": total,
                    "page": page,
                    "limit": limit,
                    "totalPages": (total + limit - 1) // limit,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": f"Failed to fetch containers: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request):
        """Create a new container."""
        # Check admin permission
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin authentication required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from .serializers import ContainerSerializer

            serializer = ContainerSerializer(data=request.data)
            if serializer.is_valid():
                container = serializer.save()
                return Response(
                    {
                        "message": "Container created successfully",
                        "data": ContainerSerializer(container).data,
                    },
                    status=status.HTTP_201_CREATED,
                )

            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except IntegrityError:
            return Response(
                {"error": "Container number already exists"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to create container: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AdminContainerDetailView(APIView):
    """Admin view for retrieving, updating, and deleting specific containers."""

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        """Check if user has admin privileges."""
        return (
            user.is_staff
            or user.is_superuser
            or (hasattr(user, "role") and user.role == "admin")
        )

    def get(self, request, container_id):
        """Get detailed information about a specific container."""
        # Check admin permission
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin authentication required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            container = Container.objects.get(id=container_id)
            from .serializers import ContainerDetailSerializer

            serializer = ContainerDetailSerializer(container)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Container.DoesNotExist:
            return Response(
                {"error": "Container not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch container: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def put(self, request, container_id):
        """Update a container."""
        # Check admin permission
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin authentication required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            container = Container.objects.get(id=container_id)
            from .serializers import ContainerSerializer

            serializer = ContainerSerializer(container, data=request.data, partial=True)
            if serializer.is_valid():
                container = serializer.save()
                return Response(
                    {
                        "message": "Container updated successfully",
                        "data": ContainerSerializer(container).data,
                    },
                    status=status.HTTP_200_OK,
                )

            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Container.DoesNotExist:
            return Response(
                {"error": "Container not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update container: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request, container_id):
        """Delete a container."""
        # Check admin permission
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin authentication required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            container = Container.objects.get(id=container_id)
            container_number = container.container_number
            container.delete()

            return Response(
                {"message": f"Container {container_number} deleted successfully"},
                status=status.HTTP_200_OK,
            )

        except Container.DoesNotExist:
            return Response(
                {"error": "Container not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to delete container: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ContainerMarkStatsView(APIView):
    """View for getting mark ID statistics for a specific container."""

    permission_classes = [IsAuthenticated]

    def get(self, request, container_id):
        """Get statistics grouped by mark ID for a container."""
        try:
            container = Container.objects.get(id=container_id)

            # Get mark ID stats
            stats = container.get_mark_id_stats()

            # Format the response
            formatted_stats = [
                {
                    "shipping_mark": item["shipping_mark"],
                    "tracking_count": item["count"],
                    "total_cbm": float(item["total_cbm"] or 0),
                    "total_shipping_fee": float(item["total_fee"] or 0),
                }
                for item in stats
            ]

            return Response(
                {
                    "container_number": container.container_number,
                    "total_trackings": container.get_tracking_count(),
                    "unique_marks": len(formatted_stats),
                    "mark_stats": formatted_stats,
                },
                status=status.HTTP_200_OK,
            )

        except Container.DoesNotExist:
            return Response(
                {"error": "Container not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch statistics: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Shipping Rate views
class ShippingRateView(APIView):
    """
    GET: Retrieve the current active shipping rate
    POST: Create or update shipping rates (Admin only)
    """

    permission_classes = [AllowAny]  # GET is public, but POST checks admin

    def get(self, request):
        """Get the active shipping rate"""
        try:
            rate = ShippingRate.objects.filter(is_active=True).first()
            if rate:
                serializer = ShippingRateSerializer(rate)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(
                {"message": "No active shipping rate found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create or update shipping rates (Admin only)"""
        # Check if user is admin
        user = getattr(request, "user", None)
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False

        if not is_admin:
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ShippingRateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShippingRateListView(generics.ListAPIView):
    """List all shipping rates (Admin only)"""

    queryset = ShippingRate.objects.all()
    serializer_class = ShippingRateSerializer
    permission_classes = [IsAdminUser]


# Admin Shipping Address Management Views
class AdminShippingAddressListCreateView(APIView):
    """
    GET: List shipping addresses with pagination, sorting, and search (Admin only)
    POST: Create a new shipping address (Admin only)
    """

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        """Check if user is admin"""
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def get(self, request):
        """List all shipping addresses with pagination, sorting, and search"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get query parameters
        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 20))
        sort_field = request.query_params.get("sortField", "created_at")
        sort_direction = request.query_params.get("sortDirection", "desc")
        search = request.query_params.get("search", "")

        # Map frontend field names to model fields
        field_mapping = {
            "markId": "mark_id",
            "name": "name",
            "createdAt": "created_at",
            "updatedAt": "updated_at",
        }
        db_sort_field = field_mapping.get(sort_field, "created_at")

        # Build queryset
        queryset = ShippingAddress.objects.all()

        # Apply search filter
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(mark_id__icontains=search)
                | Q(name__icontains=search)
                | Q(full_address__icontains=search)
                | Q(shipping_mark__icontains=search)
            )

        # Apply sorting
        if sort_direction == "desc":
            queryset = queryset.order_by(f"-{db_sort_field}")
        else:
            queryset = queryset.order_by(db_sort_field)

        # Get total count
        total = queryset.count()

        # Apply pagination
        start = (page - 1) * limit
        end = start + limit
        paginated_data = queryset[start:end]

        # Serialize
        serializer = ShippingAddressSerializer(paginated_data, many=True)

        return Response(
            {
                "data": serializer.data,
                "total": total,
                "page": page,
                "limit": limit,
                "totalPages": (total + limit - 1) // limit,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        """Create a new shipping address"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ShippingAddressSerializer(data=request.data)
        if serializer.is_valid():
            # Set created_by to current user
            try:
                user_profile = UserModel.objects.get(username=request.user.username)
                serializer.save(created_by=user_profile)
            except UserModel.DoesNotExist:
                serializer.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdminShippingAddressDetailView(APIView):
    """
    GET: Retrieve a specific shipping address (Admin only)
    PUT: Update a shipping address (Admin only)
    DELETE: Delete a shipping address (Admin only)
    """

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        """Check if user is admin"""
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def get(self, request, pk):
        """Get a specific shipping address"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            address = ShippingAddress.objects.get(pk=pk)
            serializer = ShippingAddressSerializer(address)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except ShippingAddress.DoesNotExist:
            return Response(
                {"error": "Shipping address not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def put(self, request, pk):
        """Update a shipping address"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            address = ShippingAddress.objects.get(pk=pk)
            serializer = ShippingAddressSerializer(
                address, data=request.data, partial=True
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ShippingAddress.DoesNotExist:
            return Response(
                {"error": "Shipping address not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    def delete(self, request, pk):
        """Delete a shipping address"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            address = ShippingAddress.objects.get(pk=pk)
            address.delete()
            return Response(
                {"message": "Shipping address deleted successfully"},
                status=status.HTTP_200_OK,
            )
        except ShippingAddress.DoesNotExist:
            return Response(
                {"error": "Shipping address not found"},
                status=status.HTTP_404_NOT_FOUND,
            )


class AdminDefaultBaseAddressView(APIView):
    """
    GET: Retrieve the active default base address (Admin only)
    POST: Create or update the default base address (Admin only)
    """

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        """Check if user is admin"""
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def get(self, request):
        """Get the active default base address"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            base_address = DefaultBaseAddress.objects.filter(is_active=True).first()
            if base_address:
                serializer = DefaultBaseAddressSerializer(base_address)
                return Response(serializer.data, status=status.HTTP_200_OK)

            # Return default if none exists
            return Response(
                {
                    "baseAddress": "FOFOOFOIMPORT  Phone number :18084390850 Address:广东省深圳市宝安区石岩街道金台路7号伟建产业园B栋106户*fofoofo 加纳 "
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        """Create or update the default base address"""
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        base_address_text = request.data.get("baseAddress", "")
        if not base_address_text:
            return Response(
                {"error": "baseAddress is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get or create the active base address
        base_address = DefaultBaseAddress.objects.filter(is_active=True).first()

        if base_address:
            # Update existing
            base_address.base_address = base_address_text
            try:
                user_profile = UserModel.objects.get(username=request.user.username)
                base_address.updated_by = user_profile
            except UserModel.DoesNotExist:
                pass
            base_address.save()
        else:
            # Create new
            try:
                user_profile = UserModel.objects.get(username=request.user.username)
                base_address = DefaultBaseAddress.objects.create(
                    base_address=base_address_text,
                    is_active=True,
                    updated_by=user_profile,
                )
            except UserModel.DoesNotExist:
                base_address = DefaultBaseAddress.objects.create(
                    base_address=base_address_text, is_active=True
                )

        serializer = DefaultBaseAddressSerializer(base_address)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminAlipayPaymentsView(APIView):
    """
    GET /api/admin/alipay-payments
      - Query params: page, limit, status
    DELETE handled in AdminAlipayPaymentDetailView
    """

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def get(self, request):
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        page = int(request.query_params.get("page", 1))
        limit = int(request.query_params.get("limit", 10))
        status_filter = request.query_params.get("status")

        qs = AlipayPayment.objects.all()
        if status_filter:
            qs = qs.filter(status=status_filter)

        total = qs.count()
        start = (page - 1) * limit
        end = start + limit
        items = qs.order_by("-created_at")[start:end]

        serializer = AlipayPaymentSerializer(items, many=True)
        return Response(
            {
                "data": serializer.data,
                "page": page,
                "limit": limit,
                "total": total,
                "totalPages": (total + limit - 1) // limit,
            }
        )


class AdminAlipayPaymentDetailView(APIView):
    """
    DELETE /api/admin/alipay-payments/<pk>
    """

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def delete(self, request, pk):
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            payment = AlipayPayment.objects.get(pk=pk)
            payment.delete()
            return Response({"message": "Payment deleted"}, status=status.HTTP_200_OK)
        except AlipayPayment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class AdminAlipayPaymentStatusView(APIView):
    """
    PUT /api/admin/alipay-payments/<pk>/status
    Body: { status, adminNotes?, transactionId? }
    Returns updated payment (serialized for frontend).
    """

    permission_classes = [IsAuthenticated]

    def _is_admin(self, user):
        is_admin = bool(
            getattr(user, "is_staff", False) or getattr(user, "is_superuser", False)
        )
        if not is_admin:
            try:
                profile = UserModel.objects.get(username=user.username)
                is_admin = profile.role == "admin"
            except Exception:
                is_admin = False
        return is_admin

    def put(self, request, pk):
        if not self._is_admin(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            payment = AlipayPayment.objects.get(pk=pk)
        except AlipayPayment.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status")
        admin_notes = request.data.get("adminNotes", "")
        transaction_id = request.data.get("transactionId", "")

        if new_status not in {"pending", "processing", "completed", "rejected"}:
            return Response(
                {"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Update fields
        payment.status = new_status
        payment.admin_notes = admin_notes or ""
        payment.transaction_id = transaction_id or ""

        # Set timestamps based on transitions
        now = timezone.now()
        if new_status in {"processing", "completed"} and payment.payment_date is None:
            payment.payment_date = now
        if new_status == "completed":
            payment.completion_date = now

        payment.save()

        # Notify user about status update
        try:
            if payment.user_id:
                from buysellapi.email_utils import send_notification_email
                from django.conf import settings

                user = payment.user
                subject = (
                    f"Alipay Payment Status Updated: {payment.status.capitalize()}"
                )

                amount_line = f"{payment.original_currency} {payment.original_amount}"
                converted_line = (
                    f"{payment.converted_currency} {payment.converted_amount}"
                    if payment.converted_amount is not None
                    else "N/A"
                )
                rate_text = (
                    f"{payment.exchange_rate:.3f}"
                    if payment.exchange_rate is not None
                    else "-"
                )
                txn_text = payment.transaction_id or "N/A"

                message = f"""
Hello {user.full_name or user.username},

The status of your Alipay payment request has been updated to: {payment.status.upper()}.

Details:
- Original Amount: {amount_line}
- Converted Amount: {converted_line}
- Exchange Rate (GHS→CNY): {rate_text}
- Transaction ID: {txn_text}
- Admin Notes: {(payment.admin_notes or 'N/A')}

Best regards,
{settings.SITE_NAME} Team
"""

                html_message = f"""
                <html>
                <body style=\"font-family: Arial, sans-serif; color: #333; line-height: 1.6;\">
                    <div style=\"max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 10px;\">
                        <div style=\"background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%); padding: 18px; border-radius: 8px; color: white;\">
                            <h2 style=\"margin: 0;\">Alipay Payment Status Updated</h2>
                        </div>
                        <p style=\"margin-top: 16px;\">Hello <strong>{user.full_name or user.username}</strong>,</p>
                        <p>The status of your Alipay payment request has been updated to: <strong style=\"text-transform:uppercase;\">{payment.status}</strong>.</p>
                        <table style=\"width:100%; border-collapse: collapse; background:#fff;\">
                            <tr><td style=\"padding:8px; color:#6b7280;\">Original Amount</td><td style=\"padding:8px; text-align:right;\">{amount_line}</td></tr>
                            <tr><td style=\"padding:8px; color:#6b7280;\">Converted Amount</td><td style=\"padding:8px; text-align:right;\">{converted_line}</td></tr>
                            <tr><td style=\"padding:8px; color:#6b7280;\">Exchange Rate (GHS→CNY)</td><td style=\"padding:8px; text-align:right;\">{rate_text}</td></tr>
                            <tr><td style=\"padding:8px; color:#6b7280;\">Transaction ID</td><td style=\"padding:8px; text-align:right;\">{txn_text}</td></tr>
                            {f'<tr><td style=\\"padding:8px; color:#6b7280;\\">Admin Notes</td><td style=\\"padding:8px; text-align:right;\\">{payment.admin_notes}</td></tr>' if payment.admin_notes else ''}
                        </table>
                        <p style=\"margin-top: 24px; color:#6b7280; font-size: 14px;\">Best regards,<br><strong>{settings.SITE_NAME} Team</strong></p>
                    </div>
                </body>
                </html>
                """

                send_notification_email(
                    user=user,
                    notification_type="alipay_payment_status",
                    subject=subject,
                    message=message,
                    html_message=html_message,
                )
        except Exception as e:
            logger.error(f"Failed to send alipay status email: {e}")

        serializer = AlipayPaymentSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicAlipayPaymentCreateView(APIView):
    """
    POST /api/alipay-payments
    Public endpoint for users to submit an Alipay payment order.
    If authenticated, associates the payment with the current user.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.copy()

        # Attach user if authenticated
        try:
            if getattr(request.user, "is_authenticated", False):
                user_profile = UserModel.objects.get(username=request.user.username)
                data["user"] = user_profile.id
        except UserModel.DoesNotExist:
            pass

        # Default the exchange rate to current Alipay ghs_to_cny if not provided
        if not data.get("exchangeRate") and not data.get("exchange_rate"):
            try:
                current = AlipayExchangeRate.get_current()
                data["exchangeRate"] = str(current.ghs_to_cny)
            except Exception:
                pass

        # Validate proof of payment is provided
        if not data.get("proofOfPayment"):
            return Response(
                {"error": "Proof of payment is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AlipayPaymentSerializer(data=data)
        if serializer.is_valid():
            payment = serializer.save()

            # Send acknowledgment email/notification to the user if available
            try:
                if payment.user_id:
                    from buysellapi.email_utils import send_notification_email
                    from django.conf import settings

                    user = payment.user
                    subject = "Alipay Payment Request Received"

                    amount_line = (
                        f"{payment.original_currency} {payment.original_amount}"
                    )
                    converted_line = (
                        f"{payment.converted_currency} {payment.converted_amount}"
                        if payment.converted_amount is not None
                        else "N/A"
                    )
                    rate_text = (
                        f"{payment.exchange_rate:.3f}"
                        if payment.exchange_rate is not None
                        else "-"
                    )

                    message = f"""
Hello {user.full_name or user.username},

We've received your Alipay payment request and will start processing it shortly.

Details:
- Account Type: {payment.account_type}
- Alipay Account: {payment.alipay_account}
- Original Amount: {amount_line}
- Converted Amount: {converted_line}
- Exchange Rate (GHS→CNY): {rate_text}
- Platform: {payment.platform_source or 'N/A'}
- Status: {payment.status}

We'll notify you once there's an update to the status of your request.

Best regards,
{settings.SITE_NAME} Team
"""

                    html_message = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e5e7eb; border-radius: 10px;">
                            <div style="background: linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%); padding: 18px; border-radius: 8px; color: white;">
                                <h2 style="margin: 0;">Alipay Payment Request Received</h2>
                            </div>
                            <p style="margin-top: 16px;">Hello <strong>{user.full_name or user.username}</strong>,</p>
                            <p>We've received your Alipay payment request and will start processing it shortly.</p>
                            <table style="width:100%; border-collapse: collapse; background:#fff;">
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Account Type</td>
                                    <td style="padding:8px; text-align:right;">{payment.account_type}</td>
                                </tr>
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Alipay Account</td>
                                    <td style="padding:8px; text-align:right;">{payment.alipay_account}</td>
                                </tr>
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Original Amount</td>
                                    <td style="padding:8px; text-align:right;">{amount_line}</td>
                                </tr>
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Converted Amount</td>
                                    <td style="padding:8px; text-align:right;">{converted_line}</td>
                                </tr>
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Exchange Rate (GHS→CNY)</td>
                                    <td style="padding:8px; text-align:right;">{rate_text}</td>
                                </tr>
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Platform</td>
                                    <td style="padding:8px; text-align:right;">{payment.platform_source or 'N/A'}</td>
                                </tr>
                                <tr>
                                    <td style="padding:8px; color:#6b7280;">Status</td>
                                    <td style="padding:8px; text-align:right; text-transform:capitalize;">{payment.status}</td>
                                </tr>
                            </table>

                            <p style="margin-top: 16px;">We'll notify you once there's an update to the status of your request.</p>
                            <p style="margin-top: 24px; color:#6b7280; font-size: 14px;">Best regards,<br><strong>{settings.SITE_NAME} Team</strong></p>
                        </div>
                    </body>
                    </html>
                    """

                    send_notification_email(
                        user=user,
                        notification_type="alipay_payment_submitted",
                        subject=subject,
                        message=message,
                        html_message=html_message,
                    )
            except Exception as e:
                logger.error(f"Failed to send alipay submission email: {e}")

            return Response(
                AlipayPaymentSerializer(payment).data, status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AlipayExchangeRateView(APIView):
    """
    GET: Current Alipay exchange rate (CNY<->GHS)
    POST: Update rate (admin only). Accepts ghs_to_cny or cny_to_ghs, computes the other.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest = AlipayExchangeRate.objects.first()
        if latest:
            return Response(AlipayExchangeRateSerializer(latest).data)
        temp = AlipayExchangeRate.get_current()
        ser = AlipayExchangeRateSerializer(temp)
        return Response(ser.data)

    def post(self, request):
        # Admin check
        django_user = getattr(request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if (
            not is_admin
            and django_user
            and getattr(django_user, "is_authenticated", False)
        ):
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        if not is_admin:
            raise PermissionDenied("Admin access required")

        ghs_to_cny = request.data.get("ghs_to_cny")
        cny_to_ghs = request.data.get("cny_to_ghs")

        try:
            if ghs_to_cny is None and cny_to_ghs is None:
                return Response(
                    {"error": "Provide ghs_to_cny or cny_to_ghs"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            from decimal import Decimal, ROUND_HALF_UP

            quant = Decimal("0.001")

            if ghs_to_cny is not None:
                ghs_to_cny = Decimal(str(ghs_to_cny))
                if ghs_to_cny <= 0:
                    return Response(
                        {"error": "ghs_to_cny must be > 0"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                cny_to_ghs = (Decimal(1) / ghs_to_cny).quantize(
                    quant, rounding=ROUND_HALF_UP
                )
            else:
                cny_to_ghs = Decimal(str(cny_to_ghs))
                if cny_to_ghs <= 0:
                    return Response(
                        {"error": "cny_to_ghs must be > 0"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                ghs_to_cny = (Decimal(1) / cny_to_ghs).quantize(
                    quant, rounding=ROUND_HALF_UP
                )

            # Quantize inputs as well to 3dp
            ghs_to_cny = ghs_to_cny.quantize(quant, rounding=ROUND_HALF_UP)
            cny_to_ghs = cny_to_ghs.quantize(quant, rounding=ROUND_HALF_UP)

            updated_by_user = None
            if django_user and getattr(django_user, "is_authenticated", False):
                try:
                    updated_by_user = UserModel.objects.get(
                        username=django_user.username
                    )
                except UserModel.DoesNotExist:
                    pass

            rate = AlipayExchangeRate.objects.create(
                ghs_to_cny=ghs_to_cny,
                cny_to_ghs=cny_to_ghs,
                updated_by=updated_by_user,
                notes=request.data.get("notes", ""),
            )
            return Response(
                AlipayExchangeRateSerializer(rate).data, status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AlipayExchangeRateHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Admin only
        django_user = getattr(request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if (
            not is_admin
            and django_user
            and getattr(django_user, "is_authenticated", False)
        ):
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        if not is_admin:
            raise PermissionDenied("Admin access required")

        rates = AlipayExchangeRate.objects.all()[:20]
        return Response(AlipayExchangeRateSerializer(rates, many=True).data)


class AdminSendNotificationView(APIView):
    """
    POST /api/admin/notifications/send
    Send email notification to specific user(s)

    Required permissions: Admin only
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        from .email_utils import send_admin_announcement

        user_id = request.data.get("user_id")
        subject = request.data.get("subject")
        message = request.data.get("message")

        if not all([user_id, subject, message]):
            return Response(
                {"error": "user_id, subject, and message are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = UserModel.objects.get(id=user_id)
            send_admin_announcement(
                user, announcement_subject=subject, announcement_message=message
            )
            return Response(
                {"success": True, "message": f"Notification sent to {user.email}"},
                status=status.HTTP_200_OK,
            )
        except UserModel.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AdminBroadcastNotificationView(APIView):
    """
    POST /api/admin/notifications/broadcast
    Send email notification to multiple users

    Body:
    - subject: Email subject
    - message: Email message
    - user_ids: (optional) List of specific user IDs. If omitted, sends to all non-admin users
    - role_filter: (optional) Send only to users with specific role ('customer', etc)

    Required permissions: Admin only
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        from .email_utils import send_admin_announcement

        subject = request.data.get("subject")
        message = request.data.get("message")
        user_ids = request.data.get("user_ids", [])
        role_filter = request.data.get("role_filter")

        if not all([subject, message]):
            return Response(
                {"error": "subject and message are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Build query for target users
            if user_ids:
                users = UserModel.objects.filter(id__in=user_ids)
            elif role_filter:
                users = UserModel.objects.filter(role=role_filter)
            else:
                # Send to all non-admin users
                users = UserModel.objects.exclude(role="admin")

            success_count = 0
            failed_count = 0

            for user in users:
                try:
                    send_admin_announcement(
                        user, announcement_subject=subject, announcement_message=message
                    )
                    success_count += 1
                except Exception as e:
                    failed_count += 1
                    print(f"Failed to send to {user.email}: {str(e)}")

            return Response(
                {
                    "success": True,
                    "message": f"Sent to {success_count} users, {failed_count} failed",
                    "details": {
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "total_users": users.count(),
                    },
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class NotificationHistoryView(APIView):
    """
    GET /api/admin/notifications/history
    View history of sent email notifications

    Query params:
    - user_id: Filter by specific user
    - notification_type: Filter by type (tracking_update, welcome, etc)
    - status: Filter by status (pending, sent, failed, bounced)
    - limit: Number of results (default 50)

    Required permissions: Admin only
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from .models import EmailNotification
        from .serializers import EmailNotificationSerializer

        # Get query parameters
        user_id = request.query_params.get("user_id")
        notification_type = request.query_params.get("notification_type")
        email_status = request.query_params.get("status")
        limit = int(request.query_params.get("limit", 50))

        # Build query
        queryset = EmailNotification.objects.all()

        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        if email_status:
            queryset = queryset.filter(status=email_status)

        # Order by most recent and limit
        notifications = queryset.order_by("-created_at")[:limit]

        serializer = EmailNotificationSerializer(notifications, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserNotificationsView(APIView):
    """
    GET /api/notifications/me
    Get email notifications for the authenticated user

    Query params:
    - limit: Number of results (default 20)
    - unread_only: If 'true', return only unread notifications

    Required permissions: Authenticated user
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import EmailNotification
        from .serializers import EmailNotificationSerializer

        # Get current user
        try:
            user_profile = UserModel.objects.get(username=request.user.username)
        except UserModel.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        # Get query parameters
        limit = int(request.query_params.get("limit", 20))
        unread_only = request.query_params.get("unread_only", "").lower() == "true"

        # Build query for user's notifications
        queryset = EmailNotification.objects.filter(user=user_profile)

        # Order by most recent
        notifications = queryset.order_by("-created_at")[:limit]

        serializer = EmailNotificationSerializer(notifications, many=True)

        # Add unread count
        unread_count = EmailNotification.objects.filter(
            user=user_profile, status="sent"
        ).count()

        return Response(
            {
                "notifications": serializer.data,
                "unread_count": unread_count,
                "total_count": queryset.count(),
            },
            status=status.HTTP_200_OK,
        )


class AdminNotificationsView(APIView):
    """
    GET /api/admin/notifications/me
    Get notifications for admin users (user signups, new shipments, etc.)

    Query params:
    - limit: Number of results (default 50)
    - unread_only: If 'true', return only unread notifications

    Required permissions: Admin only
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Check if user is admin
        if not is_admin_user(request.user):
            return Response(
                {"error": "Admin permission required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        from .models import EmailNotification
        from .serializers import EmailNotificationSerializer

        # Get current admin user
        try:
            admin_user = UserModel.objects.get(username=request.user.username)
        except UserModel.DoesNotExist:
            # If UserModel doesn't exist but user is authenticated as admin, create a minimal profile
            # or return empty notifications
            return Response(
                {
                    "notifications": [],
                    "unread_count": 0,
                    "total_count": 0,
                },
                status=status.HTTP_200_OK,
            )

        # Get query parameters
        limit = int(request.query_params.get("limit", 50))
        unread_only = request.query_params.get("unread_only", "").lower() == "true"

        # Build query for admin notifications
        queryset = EmailNotification.objects.filter(
            user=admin_user, notification_type="admin_notification"
        )

        if unread_only:
            queryset = queryset.filter(status="sent")

        # Order by most recent
        notifications = queryset.order_by("-created_at")[:limit]

        serializer = EmailNotificationSerializer(notifications, many=True)

        # Count unread notifications (status='sent' means unread for display purposes)
        unread_count = EmailNotification.objects.filter(
            user=admin_user, notification_type="admin_notification", status="sent"
        ).count()

        return Response(
            {
                "notifications": serializer.data,
                "unread_count": unread_count,
                "total_count": queryset.count(),
            },
            status=status.HTTP_200_OK,
        )


class MarkNotificationReadView(APIView):
    """
    PATCH /api/notifications/<id>/mark-read
    Mark a notification as read

    Required permissions: Authenticated user (can only mark their own notifications)
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, notification_id):
        from .models import EmailNotification

        try:
            # Get current user
            user_profile = UserModel.objects.get(username=request.user.username)

            # Get notification and verify ownership
            notification = EmailNotification.objects.get(
                id=notification_id, user=user_profile
            )

            # Mark as read by changing status to 'read'
            notification.status = "read"
            notification.save()

            return Response(
                {"success": True, "message": "Notification marked as read"},
                status=status.HTTP_200_OK,
            )

        except UserModel.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except EmailNotification.DoesNotExist:
            return Response(
                {"error": "Notification not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MarkAllNotificationsReadView(APIView):
    """
    POST /api/notifications/mark-all-read
    Mark all notifications as read for the authenticated user

    Required permissions: Authenticated user
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import EmailNotification

        try:
            # Get current user
            user_profile = UserModel.objects.get(username=request.user.username)

            # Update all sent (unread) notifications to read
            updated_count = EmailNotification.objects.filter(
                user=user_profile, status="sent"
            ).update(status="read")

            return Response(
                {
                    "success": True,
                    "message": f"Marked {updated_count} notifications as read",
                    "count": updated_count,
                },
                status=status.HTTP_200_OK,
            )

        except UserModel.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteNotificationView(APIView):
    """DELETE /api/notifications/<id>/
    Delete a single notification belonging to the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, notification_id):
        from .models import EmailNotification

        try:
            user_profile = UserModel.objects.get(username=request.user.username)
        except UserModel.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            notification = EmailNotification.objects.get(
                id=notification_id, user=user_profile
            )
            notification.delete()
            return Response(
                {"success": True, "message": "Notification deleted"},
                status=status.HTTP_200_OK,
            )
        except EmailNotification.DoesNotExist:
            return Response(
                {"error": "Notification not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ClearAllNotificationsView(APIView):
    """DELETE /api/notifications/clear-all/
    Permanently delete all notifications for the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        from .models import EmailNotification

        try:
            user_profile = UserModel.objects.get(username=request.user.username)
        except UserModel.DoesNotExist:
            return Response(
                {"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND
            )

        try:
            qs = EmailNotification.objects.filter(user=user_profile)
            count = qs.count()
            qs.delete()
            return Response(
                {
                    "success": True,
                    "message": f"Deleted {count} notifications",
                    "count": count,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CurrencyRateView(APIView):
    """
    GET: Get current exchange rate
    POST: Update exchange rate (admin only)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get the current USD to GHS exchange rate."""
        from .models import CurrencyRate
        from .serializers import CurrencyRateSerializer

        latest = CurrencyRate.objects.first()
        if latest:
            serializer = CurrencyRateSerializer(latest)
            return Response(serializer.data)
        else:
            # Return default rate if none exists
            return Response(
                {"usd_to_ghs": 12.0, "notes": "Default rate - no rate set yet"}
            )

    def post(self, request):
        """Update the exchange rate (admin only)."""
        # Admin check
        django_user = getattr(request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if (
            not is_admin
            and django_user
            and getattr(django_user, "is_authenticated", False)
        ):
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        if not is_admin:
            raise PermissionDenied("Admin access required")

        from .models import CurrencyRate
        from .serializers import CurrencyRateSerializer

        # Get UserModel instance for updated_by
        updated_by_user = None
        if django_user and getattr(django_user, "is_authenticated", False):
            try:
                updated_by_user = UserModel.objects.get(username=django_user.username)
            except UserModel.DoesNotExist:
                pass

        # Create new rate
        serializer = CurrencyRateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(updated_by=updated_by_user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrencyRateHistoryView(APIView):
    """GET: Get history of exchange rate changes (admin only)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Admin check
        django_user = getattr(request, "user", None)
        is_admin = bool(
            getattr(django_user, "is_staff", False)
            or getattr(django_user, "is_superuser", False)
        )
        if (
            not is_admin
            and django_user
            and getattr(django_user, "is_authenticated", False)
        ):
            try:
                profile = UserModel.objects.get(username=django_user.username)
                is_admin = profile.role == "admin"
            except UserModel.DoesNotExist:
                is_admin = False
        if not is_admin:
            raise PermissionDenied("Admin access required")

        from .models import CurrencyRate
        from .serializers import CurrencyRateSerializer

        rates = CurrencyRate.objects.all()[:20]  # Last 20 changes
        serializer = CurrencyRateSerializer(rates, many=True)
        return Response(serializer.data)


class OrderListView(generics.ListCreateAPIView):
    """List and create orders. Users can only see their own orders."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        """Users can only see their own orders."""
        user = self.request.user
        try:
            user_profile = UserModel.objects.get(username=user.username)
            return Order.objects.filter(user=user_profile).order_by('-created_at')
        except UserModel.DoesNotExist:
            return Order.objects.none()
    
    def create(self, request, *args, **kwargs):
        """Create order with better error handling."""
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            # Log validation errors for debugging
            logger.error(f"Order validation errors: {serializer.errors}")
            logger.error(f"Request data: {request.data}")
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Associate with user
        user = request.user
        try:
            user_profile = UserModel.objects.get(username=user.username)
        except UserModel.DoesNotExist:
            return Response(
                {"user": "User profile not found"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save order
        try:
            order = serializer.save(user=user_profile)
            logger.info(f"Order created successfully: ID={order.id}, User={user_profile.username}, Total={order.total}")
        except Exception as e:
            logger.error(f"Error saving order: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to create order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Verify order was saved
        try:
            saved_order = Order.objects.get(id=order.id)
            logger.info(f"Order verified in database: ID={saved_order.id}")
        except Order.DoesNotExist:
            logger.error(f"Order {order.id} was not found in database after creation!")
            return Response(
                {"error": "Order was not saved to database"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Send email notifications
        try:
            from buysellapi.email_utils import send_order_confirmation_email, notify_admin_new_order
            
            # Send confirmation email to customer
            send_order_confirmation_email(order)
            logger.info(f"Order confirmation email sent to {order.customer_email}")
            
            # Notify all admins about the new order
            notify_admin_new_order(order)
            logger.info("Admin notification emails sent for new order")
        except Exception as e:
            # Log error but don't fail the order creation
            logger.error(f"Failed to send order notification emails: {str(e)}", exc_info=True)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AdminOrderListView(APIView):
    """Admin view to list all orders."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all orders (admin only)."""
        if not is_admin_user(request.user):
            return Response(
                {"error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        orders = Order.objects.all().order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete an order. Users can only access their own orders."""
    
    permission_classes = [IsAuthenticated]
    serializer_class = OrderSerializer
    
    def get_queryset(self):
        """Users can only access their own orders, admins can access all."""
        user = self.request.user
        if is_admin_user(user):
            return Order.objects.all()
        
        try:
            user_profile = UserModel.objects.get(username=user.username)
            return Order.objects.filter(user=user_profile)
        except UserModel.DoesNotExist:
            return Order.objects.none()
    
    def get(self, request, *args, **kwargs):
        """Retrieve order details."""
        return super().get(request, *args, **kwargs)
    
    def put(self, request, *args, **kwargs):
        """Update order (typically for status updates by admin)."""
        instance = self.get_object()
        data = request.data.copy()
        
        # Check if user is admin (admins can update any order)
        user = request.user
        is_admin = is_admin_user(user)
        
        # Non-admins can only update their own orders and only certain fields
        if not is_admin:
            try:
                user_profile = UserModel.objects.get(username=user.username)
                if instance.user != user_profile:
                    return Response(
                        {"error": "You can only update your own orders"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except UserModel.DoesNotExist:
                return Response(
                    {"error": "User profile not found"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Validate status if provided
        if 'status' in data:
            valid_statuses = [choice[0] for choice in Order.STATUS_CHOICES]
            if data['status'] not in valid_statuses:
                return Response(
                    {"status": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            instance.status = data['status']
            logger.info(f"Order {instance.id} status updated to {data['status']} by {user.username}")
        
        # Validate payment_status if provided
        if 'payment_status' in data:
            valid_payment_statuses = [choice[0] for choice in Order.PAYMENT_STATUS_CHOICES]
            if data['payment_status'] not in valid_payment_statuses:
                return Response(
                    {"payment_status": f"Invalid payment status. Must be one of: {', '.join(valid_payment_statuses)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            instance.payment_status = data['payment_status']
            logger.info(f"Order {instance.id} payment_status updated to {data['payment_status']} by {user.username}")
        
        # Save the instance
        instance.save()
        
        # Return updated order
        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def delete(self, request, *args, **kwargs):
        """Delete order (only if status is pending)."""
        instance = self.get_object()
        if instance.status != 'pending':
            return Response(
                {"error": "Only pending orders can be cancelled"},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.status = 'cancelled'
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryListView(generics.ListCreateAPIView):
    """List and create categories. Public read, admin write."""
    
    queryset = Category.objects.filter(is_active=True).order_by('order', 'name')
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]  # Public can read
    
    def get_queryset(self):
        """Filter by is_active if not admin."""
        qs = Category.objects.all()
        if not self.request.user.is_authenticated or not is_admin_user(self.request.user):
            qs = qs.filter(is_active=True)
        return qs.order_by('order', 'name')
    
    def perform_create(self, serializer):
        """Only admins can create categories."""
        if not is_admin_user(self.request.user):
            raise PermissionDenied("Admin access required")
        serializer.save()


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a category. Public read, admin write."""
    
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]  # Public can read
    
    def get(self, request, *args, **kwargs):
        """Public can retrieve."""
        return super().get(request, *args, **kwargs)
    
    def put(self, request, *args, **kwargs):
        """Only admins can update."""
        if not is_admin_user(request.user):
            raise PermissionDenied("Admin access required")
        return super().put(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        """Only admins can delete."""
        if not is_admin_user(request.user):
            raise PermissionDenied("Admin access required")
        return super().delete(request, *args, **kwargs)


class ProductTypeListView(generics.ListCreateAPIView):
    """List and create product types. Public read, admin write."""
    
    queryset = ProductType.objects.filter(is_active=True).order_by('order', 'name')
    serializer_class = ProductTypeSerializer
    permission_classes = [AllowAny]  # Public can read
    
    def get_queryset(self):
        """Filter by is_active if not admin."""
        qs = ProductType.objects.all()
        if not self.request.user.is_authenticated or not is_admin_user(self.request.user):
            qs = qs.filter(is_active=True)
        return qs.order_by('order', 'name')
    
    def perform_create(self, serializer):
        """Only admins can create product types."""
        if not is_admin_user(self.request.user):
            raise PermissionDenied("Admin access required")
        serializer.save()


class ProductTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a product type. Public read, admin write."""
    
    queryset = ProductType.objects.all()
    serializer_class = ProductTypeSerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]  # Public can read
    
    def get(self, request, *args, **kwargs):
        """Public can retrieve."""
        return super().get(request, *args, **kwargs)
    
    def put(self, request, *args, **kwargs):
        """Only admins can update."""
        if not is_admin_user(request.user):
            raise PermissionDenied("Admin access required")
        return super().put(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        """Only admins can delete."""
        if not is_admin_user(request.user):
            raise PermissionDenied("Admin access required")
        return super().delete(request, *args, **kwargs)
