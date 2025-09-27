# api/views_iap.py
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from .models import PaymentReceiptIOS, Entitlement
from .serializers import IOSReceiptInSerializer
from drf_spectacular.utils import extend_schema


@extend_schema(
    request=IOSReceiptInSerializer,
    responses={200: dict},
)

class IOSReceiptIngestView(APIView):
    """
    POST /api/iap/apple/ingest/
    Принимает чек от iOS (без немедленной верификации).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ser = IOSReceiptInSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        receipt = PaymentReceiptIOS.objects.create(
            user=request.user,
            product_id=data["product_id"],
            original_transaction_id=data["original_transaction_id"],
            transaction_id=data.get("transaction_id", ""),
            bundle_id=data.get("bundle_id", ""),
            app_account_token=data.get("app_account_token", ""),
            raw_payload=data.get("raw_payload"),
            status="pending",
        )
        # здесь можно запустить async-верификацию, но ты просил просто принять чек
        return Response({
            "id": receipt.id,
            "status": receipt.status,
            "original_transaction_id": receipt.original_transaction_id,
        }, status=status.HTTP_201_CREATED)
