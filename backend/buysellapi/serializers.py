from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
import logging

logger = logging.getLogger(__name__)
from .models import (
    UserModel,
    Container,
    Tracking,
    ShippingMark,
    ShippingRate,
    ShippingAddress,
    DefaultBaseAddress,
    EmailNotification,
    Invoice,
    InvoiceItem,
    CurrencyRate,
    AlipayPayment,
    AlipayExchangeRate,
    DashboardTab,
    Product,
    ProductReview,
    Order,
    Category,
    ProductType,
    Buy4meRequest,
    QuickOrderProduct,
)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        style={"input_type": "password"},
        help_text="Password must be at least 6 characters long",
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="Enter the same password as above",
    )

    class Meta:
        model = UserModel
        fields = [
            "username",
            "full_name",
            "email",
            "password",
            "confirm_password",
            "contact",
            "location",
        ]
        extra_kwargs = {
            "email": {
                "required": True,
                "error_messages": {
                    "required": "Email address is required",
                    "invalid": "Please enter a valid email address",
                    "blank": "Email address cannot be blank",
                },
            },
            "username": {
                "help_text": "Choose a unique username (max 10 characters)",
                "error_messages": {
                    "required": "Username is required",
                    "max_length": "Username cannot exceed 10 characters",
                    "blank": "Username cannot be blank",
                    "unique": "This username is already taken. Please choose another one.",
                },
            },
            "full_name": {
                "error_messages": {
                    "required": "Full name is required",
                    "blank": "Full name cannot be blank",
                }
            },
            "contact": {
                "error_messages": {
                    "required": "Contact number is required",
                    "blank": "Contact number cannot be blank",
                    "unique": "This contact number is already registered.",
                }
            },
            "location": {
                "error_messages": {
                    "required": "Location is required",
                    "blank": "Location cannot be blank",
                }
            },
        }

    def validate_username(self, value):
        # Check against custom user table
        if UserModel.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username is already taken. Please choose another one."
            )
        # Also ensure it doesn't already exist in Django auth user table (used by JWT)
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username already exists in the system. Please choose another one."
            )
        if len(value) < 3:
            raise serializers.ValidationError(
                "Username must be at least 3 characters long."
            )
        return value

    def validate_email(self, value):
        if UserModel.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "This email is already registered. Please use a different email."
            )
        return value

    def validate_contact(self, value):
        """Validate contact number uniqueness"""
        if UserModel.objects.filter(contact=value).exists():
            raise serializers.ValidationError(
                "This contact number is already registered. Please use a different number."
            )
        return value

    def validate(self, data):
        # Check if passwords match
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError(
                {
                    "confirm_password": "Passwords do not match. Please make sure both passwords are the same."
                }
            )

        # Check password strength
        password = data["password"]
        if len(password) < 6:
            raise serializers.ValidationError(
                {"password": "Password must be at least 6 characters long."}
            )

        return data

    def create(self, validated_data):
        # Remove confirm_password from validated data
        validated_data.pop("confirm_password")

        # Keep a copy of the plain password for Django auth user creation
        plain_password = validated_data["password"]

        # Hash the password for storage in our custom user table
        validated_data["password"] = make_password(plain_password)

        # Create user in custom table
        user_model = UserModel.objects.create(**validated_data)

        # Ensure a corresponding Django auth user exists for JWT authentication
        # Only create if it doesn't already exist
        if not User.objects.filter(username=user_model.username).exists():
            User.objects.create_user(
                username=user_model.username,
                email=user_model.email,
                password=plain_password,
            )

        return user_model


class UserModelSerializer(serializers.ModelSerializer):
    shipping_mark = serializers.SerializerMethodField()

    class Meta:
        model = UserModel
        fields = "__all__"
        extra_kwargs = {"password": {"write_only": True}}

    def get_shipping_mark(self, obj):
        """Include shipping mark data if it exists for this user."""
        try:
            if hasattr(obj, "shipping_mark") and obj.shipping_mark:
                return {
                    "mark_id": obj.shipping_mark.mark_id,
                    "name": obj.shipping_mark.name,
                    "created_at": obj.shipping_mark.created_at,
                }
        except Exception:
            pass
        return None


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Allow login using either username or email together with password.

    This works for all users (including superusers). If the provided
    'username' field looks like an email or matches a User.email, we resolve
    it to the corresponding username before delegating to the base class.
    """

    def validate(self, attrs):
        username_or_email = attrs.get("username")
        password = attrs.get("password")

        if username_or_email and password:
            # Try exact username match first
            user = User.objects.filter(username=username_or_email).first()
            if not user:
                # Fallback: email (case-insensitive)
                user = (
                    User.objects.filter(email__iexact=username_or_email)
                    .order_by("-is_superuser", "-is_staff", "id")
                    .first()
                )
            if user:
                # Replace provided identifier with the real username so the
                # base serializer can authenticate properly
                attrs["username"] = user.username

        return super().validate(attrs)


class ContainerSerializer(serializers.ModelSerializer):
    """Serializer for Container model with tracking statistics."""

    tracking_count = serializers.SerializerMethodField(read_only=True)
    unique_mark_ids = serializers.SerializerMethodField(read_only=True)
    mark_id_stats = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Container
        fields = [
            "id",
            "container_number",
            "port_of_loading",
            "port_of_discharge",
            "status",
            "departure_date",
            "arrival_date",
            "notes",
            "created_at",
            "updated_at",
            "tracking_count",
            "unique_mark_ids",
            "mark_id_stats",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_tracking_count(self, obj):
        """Get total number of tracking entries in this container."""
        return obj.get_tracking_count()

    def get_unique_mark_ids(self, obj):
        """Get list of unique shipping mark IDs."""
        return obj.get_unique_mark_ids()

    def get_mark_id_stats(self, obj):
        """Get statistics grouped by mark ID."""
        return list(obj.get_mark_id_stats())


class ContainerDetailSerializer(serializers.ModelSerializer):
    """Detailed container serializer with nested tracking information."""

    trackings = serializers.SerializerMethodField(read_only=True)
    tracking_count = serializers.SerializerMethodField(read_only=True)
    mark_id_stats = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Container
        fields = [
            "id",
            "container_number",
            "port_of_loading",
            "port_of_discharge",
            "status",
            "departure_date",
            "arrival_date",
            "notes",
            "created_at",
            "updated_at",
            "tracking_count",
            "trackings",
            "mark_id_stats",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_trackings(self, obj):
        """Get all tracking entries in this container."""
        from .serializers import TrackingSerializer

        trackings = obj.trackings.all()
        return TrackingSerializer(trackings, many=True).data

    def get_tracking_count(self, obj):
        """Get total number of tracking entries."""
        return obj.get_tracking_count()

    def get_mark_id_stats(self, obj):
        """Get statistics grouped by mark ID."""
        stats = obj.get_mark_id_stats()
        return [
            {
                "shipping_mark": item["shipping_mark"],
                "count": item["count"],
                "total_cbm": float(item["total_cbm"] or 0),
                "total_fee": float(item["total_fee"] or 0),
            }
            for item in stats
        ]


class TrackingSerializer(serializers.ModelSerializer):
    owner_username = serializers.SerializerMethodField(read_only=True)
    container_number = serializers.SerializerMethodField(read_only=True)
    owner = serializers.PrimaryKeyRelatedField(
        queryset=UserModel.objects.all(),
        required=False,
        allow_null=True,
        help_text="User ID of the tracking owner (optional, defaults to authenticated user)",
    )
    container = serializers.PrimaryKeyRelatedField(
        queryset=Container.objects.all(),
        required=False,
        allow_null=True,
        help_text="Container ID this tracking belongs to (optional)",
    )

    class Meta:
        model = Tracking
        fields = [
            "id",
            "tracking_number",
            "owner",
            "owner_username",
            "container",
            "container_number",
            "shipping_mark",
            "status",
            "cbm",
            "shipping_fee",
            "goods_type",
            "date_added",
            "eta",
        ]
        read_only_fields = ["id", "date_added", "owner_username", "container_number"]
        extra_kwargs = {
            "shipping_mark": {"required": False, "allow_blank": True, "default": ""},
            "cbm": {"required": False, "allow_null": True},
            "shipping_fee": {"required": False, "allow_null": True},
            "goods_type": {"required": False, "allow_null": True},
            "eta": {"required": False, "allow_null": True},
            "container": {"required": False, "allow_null": True},
        }

    def get_owner_username(self, obj):
        try:
            return obj.owner.username if obj.owner else None
        except Exception:
            return None

    def get_container_number(self, obj):
        try:
            return obj.container.container_number if obj.container else None
        except Exception:
            return None


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model exposed to frontend.

    Fields kept simple and compatible with the frontend shop which
    expects `_id`, `name`, `price`, `image`/`images`, `category`, `type`.
    """

    _id = serializers.IntegerField(source="id", read_only=True)
    images = serializers.ListField(child=serializers.CharField(), required=False)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "_id",
            "name",
            "slug",
            "description",
            "price",
            "images",
            "category",
            "product_type",
            "inventory",
            "trending",
            "is_active",
            "created_at",
            "average_rating",
            "review_count",
        ]
        read_only_fields = ["_id", "created_at", "average_rating", "review_count"]
    
    def get_average_rating(self, obj):
        """Get average rating from approved reviews."""
        try:
            return obj.get_average_rating()
        except Exception:
            return 0.0
    
    def get_review_count(self, obj):
        """Get count of approved reviews."""
        try:
            return obj.get_review_count()
        except Exception:
            return 0


class ProductReviewSerializer(serializers.ModelSerializer):
    """Serializer for ProductReview model."""
    
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = ProductReview
        fields = [
            'id',
            'product',
            'user',
            'user_name',
            'user_id',
            'product_name',
            'rating',
            'title',
            'comment',
            'is_approved',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class ShippingMarkSerializer(serializers.ModelSerializer):
    """Serializer exposing fields to match existing frontend expectations.

    Maps backend fields to camelCase and aliases commonly used names:
    - id -> _id
    - mark_id -> markId
    - created_at -> createdAt
    Adds computed fields:
    - shippingMark -> "{markId}:{name}"
    - fullAddress -> "{markId} - {name}\n{BASE_ADDRESS}"
    """

    _id = serializers.IntegerField(source="id", read_only=True)
    markId = serializers.CharField(source="mark_id", read_only=True)
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    shippingMark = serializers.SerializerMethodField()
    fullAddress = serializers.SerializerMethodField()

    class Meta:
        model = ShippingMark
        fields = [
            "_id",
            "markId",
            "name",
            "shippingMark",
            "fullAddress",
            "createdAt",
        ]
        read_only_fields = ["_id", "markId", "shippingMark", "fullAddress", "createdAt"]

    def get_shippingMark(self, obj: ShippingMark) -> str:
        # Use user's full name instead of shipping mark name field
        user_full_name = obj.owner.full_name if obj.owner else obj.name
        return f"{obj.mark_id}:{user_full_name}"

    def get_fullAddress(self, obj: ShippingMark) -> str:
        # Prefer the active DefaultBaseAddress from backend; fallback to legacy text
        try:
            active = DefaultBaseAddress.objects.filter(is_active=True).first()
            if active and active.base_address:
                base_address = active.base_address
            else:
                base_address = "FOFOOFOIMPORT  Phone number :18084390850 Address:广东省深圳市宝安区石岩街道金台路7号伟建产业园B栋106户*fofoofo 加纳 "
        except Exception:
            base_address = "FOFOOFOIMPORT  Phone number :18084390850 Address:广东省深圳市宝安区石岩街道金台路7号伟建产业园B栋106户*fofoofo 加纳 "

        # Use user's full name instead of markId in the address
        user_full_name = obj.owner.full_name if obj.owner else obj.name
        return f"{obj.mark_id} - {user_full_name}\n{base_address}"


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id",
            "tracking",
            "description",
            "tracking_number",
            "cbm",
            "rate_per_cbm",
            "goods_type",
            "total_amount",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    container_number = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "shipping_mark",
            "customer_name",
            "customer_email",
            "subtotal",
            "tax_amount",
            "discount_amount",
            "total_amount",
            "exchange_rate",
            "total_amount_ghs",
            "status",
            "issue_date",
            "due_date",
            "paid_date",
            "payment_method",
            "payment_reference",
            "notes",
            "container",
            "container_number",
            "created_by",
            "created_at",
            "updated_at",
            "items",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "created_by",
            "container_number",
        ]

    def get_container_number(self, obj):
        try:
            return obj.container.container_number
        except Exception:
            return None


class ShippingRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingRate
        fields = [
            "id",
            "normal_goods_rate",
            "special_goods_rate",
            "normal_goods_rate_lt1",
            "special_goods_rate_lt1",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        # Ensure all provided numeric fields are positive
        for key in [
            "normal_goods_rate",
            "special_goods_rate",
            "normal_goods_rate_lt1",
            "special_goods_rate_lt1",
        ]:
            val = attrs.get(key, None)
            if val is not None and val <= 0:
                raise serializers.ValidationError({key: "Must be greater than zero"})
        return attrs


class ShippingAddressSerializer(serializers.ModelSerializer):
    """Serializer for ShippingAddress model (admin-managed addresses)."""

    _id = serializers.CharField(source="id", read_only=True)
    markId = serializers.CharField(source="mark_id")
    fullAddress = serializers.CharField(source="full_address")
    shippingMark = serializers.CharField(source="shipping_mark")
    trackingNumber = serializers.CharField(
        source="tracking_number", required=False, allow_blank=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    updatedAt = serializers.DateTimeField(source="updated_at", read_only=True)

    class Meta:
        model = ShippingAddress
        fields = [
            "_id",
            "markId",
            "name",
            "fullAddress",
            "shippingMark",
            "trackingNumber",
            "createdAt",
            "updatedAt",
        ]
        read_only_fields = ["_id", "createdAt", "updatedAt"]

    def validate_markId(self, value):
        """Ensure mark_id is unique when creating."""
        instance = self.instance
        if not instance and ShippingAddress.objects.filter(mark_id=value).exists():
            raise serializers.ValidationError(
                "A shipping address with this Mark ID already exists."
            )
        # Allow updates to keep the same mark_id
        return value


class DefaultBaseAddressSerializer(serializers.ModelSerializer):
    """Serializer for DefaultBaseAddress model."""

    baseAddress = serializers.CharField(source="base_address")

    class Meta:
        model = DefaultBaseAddress
        fields = ["id", "baseAddress", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at", "is_active"]


class EmailNotificationSerializer(serializers.ModelSerializer):
    """Serializer for EmailNotification model."""

    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)
    tracking_number = serializers.CharField(
        source="tracking.tracking_number", read_only=True, allow_null=True
    )

    class Meta:
        model = EmailNotification
        fields = [
            "id",
            "user",
            "user_email",
            "user_full_name",
            "notification_type",
            "subject",
            "message",
            "status",
            "sent_at",
            "error_message",
            "tracking",
            "tracking_number",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "sent_at"]


class OTPRequestSerializer(serializers.Serializer):
    """Request body for sending an OTP code."""

    identifier = serializers.CharField(help_text="Username or email to send the OTP to")


class OTPVerifySerializer(serializers.Serializer):
    """Request body for verifying an OTP code and obtaining tokens."""

    identifier = serializers.CharField(help_text="Username or email")
    code = serializers.CharField(min_length=4, max_length=8)


class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        help_text="Username or email to send the reset code"
    )


class PasswordResetVerifySerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="Username or email")
    code = serializers.CharField(min_length=4, max_length=8)
    new_password = serializers.CharField(min_length=6, write_only=True)
    confirm_password = serializers.CharField(min_length=6, write_only=True)

    def validate(self, attrs):
        if attrs.get("new_password") != attrs.get("confirm_password"):
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs


class CurrencyRateSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True
    )

    class Meta:
        model = CurrencyRate
        fields = [
            "id",
            "usd_to_ghs",
            "updated_by",
            "updated_by_username",
            "updated_at",
            "created_at",
            "notes",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "updated_by_username"]


class AlipayPaymentSerializer(serializers.ModelSerializer):
    """Serializer mapping to the frontend's expected field names.

    Maps snake_case to camelCase and aliases:
    - id -> _id
    - created_at -> createdAt
    - payment_date -> paymentDate
    - completion_date -> completionDate
    Includes userName derived from user's full_name or username.
    """

    _id = serializers.IntegerField(source="id", read_only=True)
    userName = serializers.SerializerMethodField()
    accountType = serializers.CharField(source="account_type")
    originalCurrency = serializers.CharField(source="original_currency")
    originalAmount = serializers.DecimalField(
        source="original_amount", max_digits=12, decimal_places=2
    )
    convertedCurrency = serializers.CharField(source="converted_currency")
    convertedAmount = serializers.DecimalField(
        source="converted_amount", max_digits=12, decimal_places=2
    )
    platformSource = serializers.CharField(source="platform_source")
    qrCodeImage = serializers.CharField(source="qr_code_image")
    realName = serializers.CharField(source="real_name")
    alipayAccount = serializers.CharField(source="alipay_account")
    proofOfPayment = serializers.CharField(
        source="proof_of_payment", required=False, allow_blank=True
    )
    exchangeRate = serializers.DecimalField(
        source="exchange_rate", max_digits=10, decimal_places=3, required=False
    )
    adminNotes = serializers.CharField(
        source="admin_notes", required=False, allow_blank=True
    )
    transactionId = serializers.CharField(
        source="transaction_id", required=False, allow_blank=True
    )
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    paymentDate = serializers.DateTimeField(
        source="payment_date", required=False, allow_null=True
    )
    completionDate = serializers.DateTimeField(
        source="completion_date", required=False, allow_null=True
    )

    class Meta:
        model = AlipayPayment
        fields = [
            "_id",
            "user",
            "userName",
            "accountType",
            "alipayAccount",
            "realName",
            "qrCodeImage",
            "proofOfPayment",
            "platformSource",
            "originalCurrency",
            "originalAmount",
            "convertedCurrency",
            "convertedAmount",
            "exchangeRate",
            "status",
            "transactionId",
            "adminNotes",
            "createdAt",
            "paymentDate",
            "completionDate",
        ]
        extra_kwargs = {
            "user": {"write_only": True, "required": False, "allow_null": True},
        }

    def get_userName(self, obj):
        try:
            if obj.user and obj.user.full_name:
                return obj.user.full_name
            return obj.user.username if obj.user else ""
        except Exception:
            return ""


class AlipayExchangeRateSerializer(serializers.ModelSerializer):
    updated_by_username = serializers.CharField(
        source="updated_by.username", read_only=True
    )

    class Meta:
        model = AlipayExchangeRate
        fields = [
            "id",
            "ghs_to_cny",
            "cny_to_ghs",
            "updated_by",
            "updated_by_username",
            "updated_at",
            "created_at",
            "notes",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "updated_by_username"]


class DashboardTabSerializer(serializers.ModelSerializer):
    """Serializer for DashboardTab exposed to frontend.

    Adds request-scoped metadata so frontend can display assignment state.
    """

    assigned = serializers.SerializerMethodField()
    assigned_to_all_admins = serializers.SerializerMethodField()

    class Meta:
        model = DashboardTab
        fields = (
            "name",
            "slug",
            "description",
            "order",
            "assigned",
            "assigned_to_all_admins",
        )

    def get_assigned(self, obj):
        try:
            request = self.context.get("request") if hasattr(self, "context") else None
            if not request or not getattr(request, "user", None):
                return False
            user = request.user
            # Direct user assignment
            try:
                # Use prefetched users if available, otherwise query
                if hasattr(obj, '_prefetched_objects_cache') and 'users' in obj._prefetched_objects_cache:
                    user_ids = [u.id for u in obj._prefetched_objects_cache['users']]
                    if user.id in user_ids:
                        return True
                else:
                    if obj.users.filter(id=user.id).exists():
                        return True
            except Exception as e:
                logger.warning(f"Error checking user assignment: {e}")
                pass
            # Group assignment
            try:
                user_groups = user.groups.all()
                if not user_groups.exists():
                    return False
                # Use prefetched groups if available
                if hasattr(obj, '_prefetched_objects_cache') and 'groups' in obj._prefetched_objects_cache:
                    group_ids = [g.id for g in obj._prefetched_objects_cache['groups']]
                    user_group_ids = [g.id for g in user_groups]
                    return any(gid in group_ids for gid in user_group_ids)
                else:
                    return obj.groups.filter(id__in=[g.id for g in user_groups]).exists()
            except Exception as e:
                logger.warning(f"Error checking group assignment: {e}")
                return False
        except Exception as e:
            logger.error(f"Error in get_assigned: {e}")
            return False

    def get_assigned_to_all_admins(self, obj):
        # Determine whether every admin (by UserModel.role == 'admin') is present in obj.users
        try:
            admin_profiles = UserModel.objects.filter(role="admin")
            if not admin_profiles.exists():
                return False
            
            # Get prefetched user IDs if available
            prefetched_user_ids = None
            if hasattr(obj, '_prefetched_objects_cache') and 'users' in obj._prefetched_objects_cache:
                prefetched_user_ids = {u.id for u in obj._prefetched_objects_cache['users']}
            
            for profile in admin_profiles:
                auth_user = User.objects.filter(username=profile.username).first()
                if not auth_user:
                    return False
                
                if prefetched_user_ids is not None:
                    if auth_user.id not in prefetched_user_ids:
                        return False
                else:
                    if not obj.users.filter(id=auth_user.id).exists():
                        return False
            return True
        except Exception as e:
            logger.error(f"Error in get_assigned_to_all_admins: {e}")
            return False


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model."""
    
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    # Ensure decimal fields are properly handled
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    shipping_cost = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    
    class Meta:
        model = Order
        fields = [
            'id',
            'user',
            'user_name',
            'user_email',
            'items',
            'customer_name',
            'customer_email',
            'customer_phone',
            'shipping_address',
            'shipping_city',
            'shipping_state',
            'shipping_zip_code',
            'shipping_country',
            'subtotal',
            'tax',
            'shipping_cost',
            'total',
            'status',
            'payment_status',
            'payment_method',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate_items(self, value):
        """Validate that items is a list."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Items must be a list.")
        if len(value) == 0:
            raise serializers.ValidationError("At least one item is required.")
        return value
    
    def validate(self, data):
        """Validate order totals."""
        subtotal = data.get('subtotal', 0)
        tax = data.get('tax', 0)
        shipping_cost = data.get('shipping_cost', 0)
        total = data.get('total', 0)
        
        # Convert to Decimal for proper comparison
        from decimal import Decimal
        try:
            subtotal = Decimal(str(subtotal))
            tax = Decimal(str(tax))
            shipping_cost = Decimal(str(shipping_cost))
            total = Decimal(str(total))
        except (ValueError, TypeError) as e:
            raise serializers.ValidationError({
                'total': f'Invalid decimal values: {e}'
            })
        
        # Calculate expected total
        expected_total = subtotal + tax + shipping_cost
        
        # Allow small rounding differences (0.01)
        if abs(float(total) - float(expected_total)) > 0.01:
            raise serializers.ValidationError({
                'total': f'Total ({total}) does not match subtotal ({subtotal}) + tax ({tax}) + shipping ({shipping_cost}) = {expected_total}'
            })
        
        return data


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model."""
    
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'is_active',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductTypeSerializer(serializers.ModelSerializer):
    """Serializer for ProductType model."""
    
    class Meta:
        model = ProductType
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'is_active',
            'order',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class Buy4meRequestSerializer(serializers.ModelSerializer):
    """Serializer for Buy4meRequest model."""
    
    user_name = serializers.CharField(source='user.full_name', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    
    # Invoice data as nested object for frontend compatibility
    invoice = serializers.SerializerMethodField()
    
    class Meta:
        model = Buy4meRequest
        fields = [
            'id',
            'user',
            'user_name',
            'user_email',
            'user_username',
            'title',
            'description',
            'product_url',
            'additional_links',
            'images',
            'quantity',
            'status',
            'tracking_status',
            'notes',
            'invoice_created',
            'invoice_number',
            'invoice_status',
            'invoice_amount',
            'invoice',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'invoice_created', 'invoice_number']
    
    def get_invoice(self, obj):
        """Return invoice data as nested object for frontend compatibility."""
        if obj.invoice_created and obj.invoice_number:
            return {
                'invoiceNumber': obj.invoice_number,
                'amount': float(obj.invoice_amount) if obj.invoice_amount else 0,
                'status': obj.invoice_status,
                'createdAt': obj.created_at.isoformat() if obj.created_at else None,
            }
        return None
    
    def validate_additional_links(self, value):
        """Validate additional_links format."""
        if not isinstance(value, list):
            raise serializers.ValidationError("additional_links must be a list.")
        for link in value:
            if not isinstance(link, dict):
                raise serializers.ValidationError("Each link must be an object with 'url' and 'quantity'.")
            if 'url' not in link or not link.get('url'):
                raise serializers.ValidationError("Each link must have a 'url' field.")
        return value
    
    def validate_product_url(self, value):
        """Validate product_url format."""
        if value and not value.startswith(('http://', 'https://')):
            # Auto-add https:// if missing
            value = 'https://' + value
        return value


class QuickOrderProductSerializer(serializers.ModelSerializer):
    """Serializer for QuickOrderProduct model."""
    
    class Meta:
        model = QuickOrderProduct
        fields = [
            'id',
            'title',
            'description',
            'product_url',
            'images',
            'min_quantity',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_product_url(self, value):
        """Validate product_url format."""
        if value and not value.startswith(('http://', 'https://')):
            # Auto-add https:// if missing
            value = 'https://' + value
        return value
