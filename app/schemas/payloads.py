"""
Rôle du fichier:
Décrit les schémas d'entrée/sortie de l'API via Pydantic pour valider les données reçues.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserRegisterSchema(BaseModel):
    """Classe UserRegisterSchema : documente ses responsabilites et son comportement."""
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=128)
    role_name: str


class LoginSchema(BaseModel):
    """Classe LoginSchema : documente ses responsabilites et son comportement."""
    username: str
    password: str


class ChangePasswordSchema(BaseModel):
    """Classe ChangePasswordSchema : documente ses responsabilites et son comportement."""
    current_password: str = Field(min_length=6, max_length=128)
    new_password: str = Field(min_length=6, max_length=128)


class EmployeeCreateSchema(BaseModel):
    """Classe EmployeeCreateSchema : documente ses responsabilites et son comportement."""
    first_name: str
    last_name: str
    photo_url: str | None = None
    email: EmailStr
    phone: str
    address: str
    hire_date: date
    status: str = "Actif"
    department_id: int | None = None
    role_id: int


class EmployeeUpdateSchema(BaseModel):
    """Classe EmployeeUpdateSchema : documente ses responsabilites et son comportement."""
    first_name: str | None = None
    last_name: str | None = None
    photo_url: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    hire_date: date | None = None
    status: str | None = None
    department_id: int | None = None
    role_id: int | None = None


class DepartmentCreateSchema(BaseModel):
    """Classe DepartmentCreateSchema : documente ses responsabilites et son comportement."""
    name: str
    budget: float = 0
    manager_id: int | None = None


class DepartmentUpdateSchema(BaseModel):
    """Classe DepartmentUpdateSchema : documente ses responsabilites et son comportement."""
    name: str | None = None
    budget: float | None = None
    manager_id: int | None = None


class RoleCreateSchema(BaseModel):
    """Classe RoleCreateSchema : documente ses responsabilites et son comportement."""
    name: str
    permission_names: list[str] = []


class PermissionAssignSchema(BaseModel):
    """Classe PermissionAssignSchema : documente ses responsabilites et son comportement."""
    permission_names: list[str]


class PayrollCreateSchema(BaseModel):
    """Classe PayrollCreateSchema : documente ses responsabilites et son comportement."""
    employee_id: int
    base_salary: float = Field(ge=0)
    bonus: float = Field(default=0, ge=0)
    overtime_hours: float = Field(default=0, ge=0)
    deductions: float = Field(default=0, ge=0)
    taxes: float = Field(default=0, ge=0)
    payroll_month: str | None = None


class PayrollUpdateSchema(BaseModel):
    """Classe PayrollUpdateSchema : documente ses responsabilites et son comportement."""
    base_salary: float | None = Field(default=None, ge=0)
    bonus: float | None = Field(default=None, ge=0)
    overtime_hours: float | None = Field(default=None, ge=0)
    deductions: float | None = Field(default=None, ge=0)
    taxes: float | None = Field(default=None, ge=0)


class AttendanceCheckInSchema(BaseModel):
    """Classe AttendanceCheckInSchema : documente ses responsabilites et son comportement."""
    employee_id: int
    check_in: datetime
    late_minutes: int = 0
    is_absent: bool = False


class AttendanceUpdateSchema(BaseModel):
    """Classe AttendanceUpdateSchema : documente ses responsabilites et son comportement."""
    check_in: datetime | None = None
    check_out: datetime | None = None
    late_minutes: int | None = None
    is_absent: bool | None = None


class AttendanceCheckOutSchema(BaseModel):
    """Classe AttendanceCheckOutSchema : documente ses responsabilites et son comportement."""
    attendance_id: int
    check_out: datetime


class AttendanceCheckoutByEmployeeSchema(BaseModel):
    """Classe AttendanceCheckoutByEmployeeSchema : documente ses responsabilites et son comportement."""
    employee_id: int
    check_out: datetime


class LeaveCreateSchema(BaseModel):
    """Classe LeaveCreateSchema : documente ses responsabilites et son comportement."""
    employee_id: int
    start_date: date
    end_date: date
    reason: str

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, value: date, info):
        """Methode validate_dates : realise une partie de la logique de la classe."""
        start_date = info.data.get("start_date")
        if start_date and value < start_date:
            raise ValueError("La date de fin doit être >= date de début")
        return value


class LeaveApprovalSchema(BaseModel):
    """Classe LeaveApprovalSchema : documente ses responsabilites et son comportement."""
    status: str
    decision_comment: str | None = None


class LeaveUpdateSchema(BaseModel):
    """Classe LeaveUpdateSchema : documente ses responsabilites et son comportement."""
    start_date: date | None = None
    end_date: date | None = None
    reason: str | None = None
    status: str | None = None
    decision_comment: str | None = None


class ContractCreateSchema(BaseModel):
    """Classe ContractCreateSchema : documente ses responsabilites et son comportement."""
    employee_id: int
    contract_type: str
    start_date: date
    end_date: date | None = None
    contractual_salary: float = Field(ge=0)
    document_path: str | None = None


class ContractUpdateSchema(BaseModel):
    """Classe ContractUpdateSchema : documente ses responsabilites et son comportement."""
    contract_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    contractual_salary: float | None = Field(default=None, ge=0)
    document_path: str | None = None


class AccountRoleUpdateSchema(BaseModel):
    """Classe AccountRoleUpdateSchema : documente ses responsabilites et son comportement."""
    role_id: int


class AccountStatusUpdateSchema(BaseModel):
    """Classe AccountStatusUpdateSchema : documente ses responsabilites et son comportement."""
    status: str


class AgentMessageCreateSchema(BaseModel):
    """Classe AgentMessageCreateSchema : documente ses responsabilites et son comportement."""
    recipient_user_id: int | None = None
    recipient_employee_id: int | None = None
    subject: str | None = Field(default=None, max_length=160)
    content: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_recipient(self):
        """Methode validate_recipient : realise une partie de la logique de la classe."""
        if not self.recipient_user_id and not self.recipient_employee_id:
            raise ValueError("recipient_user_id ou recipient_employee_id est requis")
        return self


class ChatThreadMessageSchema(BaseModel):
    """Classe ChatThreadMessageSchema : documente ses responsabilites et son comportement."""
    content: str = Field(min_length=1, max_length=2000)
    subject: str | None = Field(default=None, max_length=160)


class MessageUpdateSchema(BaseModel):
    """Classe MessageUpdateSchema : documente ses responsabilites et son comportement."""
    content: str = Field(min_length=1, max_length=2000)


class ErrorSchema(BaseModel):
    """Classe ErrorSchema : documente ses responsabilites et son comportement."""
    model_config = ConfigDict(extra="allow")
    error: str
