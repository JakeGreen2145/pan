from pan.exceptions import PanError, TenantNotFoundError

__all__ = ["TenantNotFoundError", "PaymentRecordError", "RentCalculationError"]


class PaymentRecordError(PanError):
    def __init__(self, tenant_id: str, detail: str) -> None:
        super().__init__(
            f"Failed to record payment for tenant {tenant_id}: {detail}",
            tenant_id=tenant_id,
        )


class RentCalculationError(PanError):
    def __init__(self, detail: str) -> None:
        super().__init__(f"Rent calculation error: {detail}")
