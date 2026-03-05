"""
Rôle du fichier:
Fournit un point d'accès central aux entités métier importées depuis les modèles de base.
"""

from __future__ import annotations

from datetime import date, datetime


class Person:
    """Entité de base représentant une personne avec ses informations de contact."""
    def __init__(self, first_name: str, last_name: str, email: str, phone: str, address: str):
        """Construit une personne en normalisant les champs texte principaux."""
        self.__first_name = first_name.strip()
        self.__last_name = last_name.strip()
        self.__email = email.strip().lower()
        self.__phone = phone.strip()
        self.__address = address.strip()

    @property
    def first_name(self) -> str:
        """Methode first_name : realise une partie de la logique de la classe."""
        return self.__first_name

    @property
    def last_name(self) -> str:
        """Methode last_name : realise une partie de la logique de la classe."""
        return self.__last_name

    @property
    def full_name(self) -> str:
        """Methode full_name : realise une partie de la logique de la classe."""
        return f"{self.__first_name} {self.__last_name}"

    @property
    def email(self) -> str:
        """Methode email : realise une partie de la logique de la classe."""
        return self.__email

    @property
    def phone(self) -> str:
        """Methode phone : realise une partie de la logique de la classe."""
        return self.__phone

    @property
    def address(self) -> str:
        """Methode address : realise une partie de la logique de la classe."""
        return self.__address


class EmployeeEntity(Person):
    """Entité métier d'un employé enrichissant Person avec statut, rôle et date d'embauche."""
    def __init__(
        self,
        first_name: str,
        last_name: str,
        email: str,
        phone: str,
        address: str,
        hire_date: date,
        status: str,
        role_name: str,
    ):
        super().__init__(first_name, last_name, email, phone, address)
        self.__hire_date = hire_date
        self.__status = status
        self.__role_name = role_name

    @property
    def hire_date(self) -> date:
        """Methode hire_date : realise une partie de la logique de la classe."""
        return self.__hire_date

    @property
    def status(self) -> str:
        """Methode status : realise une partie de la logique de la classe."""
        return self.__status

    @property
    def role_name(self) -> str:
        """Methode role_name : realise une partie de la logique de la classe."""
        return self.__role_name


class DeveloperEntity(EmployeeEntity):
    """Spécialisation employé orientée développement logiciel."""
    def __init__(self, *args, primary_stack: str = "Python", **kwargs):
        super().__init__(*args, **kwargs)
        self.__primary_stack = primary_stack

    @property
    def primary_stack(self) -> str:
        """Methode primary_stack : realise une partie de la logique de la classe."""
        return self.__primary_stack


class ManagerEntity(EmployeeEntity):
    """Spécialisation employé orientée management d'équipe."""
    def __init__(self, *args, team_size: int = 0, **kwargs):
        super().__init__(*args, **kwargs)
        self.__team_size = team_size

    @property
    def team_size(self) -> int:
        """Methode team_size : realise une partie de la logique de la classe."""
        return self.__team_size


class HREntity(EmployeeEntity):
    """Spécialisation employé orientée ressources humaines."""
    def __init__(self, *args, specialty: str = "Talent", **kwargs):
        super().__init__(*args, **kwargs)
        self.__specialty = specialty

    @property
    def specialty(self) -> str:
        """Methode specialty : realise une partie de la logique de la classe."""
        return self.__specialty


class DepartmentEntity:
    """Entité métier d'un département regroupant un budget et des employés."""
    def __init__(self, name: str, budget: float):
        self.__name = name
        self.__budget = budget
        self.__employees: list[EmployeeEntity] = []

    @property
    def name(self) -> str:
        """Methode name : realise une partie de la logique de la classe."""
        return self.__name

    @property
    def budget(self) -> float:
        """Methode budget : realise une partie de la logique de la classe."""
        return self.__budget

    @property
    def employees(self) -> list[EmployeeEntity]:
        """Methode employees : realise une partie de la logique de la classe."""
        return self.__employees

    def add_employee(self, employee: EmployeeEntity) -> None:
        """Ajoute un employé dans la collection interne du département."""
        self.__employees.append(employee)


class PayrollEntity:
    """Entité métier de paie permettant de calculer rapidement le salaire net."""
    def __init__(self, employee: EmployeeEntity, base_salary: float, bonus: float, overtime_hours: float, deductions: float, taxes: float):
        """Construit une paie en mémorisant les composantes financières."""
        self.__employee = employee
        self.__base_salary = base_salary
        self.__bonus = bonus
        self.__overtime_hours = overtime_hours
        self.__deductions = deductions
        self.__taxes = taxes
        self.__created_at = datetime.utcnow()

    @property
    def employee(self) -> EmployeeEntity:
        """Methode employee : realise une partie de la logique de la classe."""
        return self.__employee

    @property
    def net_salary(self) -> float:
        """Methode net_salary : realise une partie de la logique de la classe."""
        return round(self.__base_salary + self.__bonus + self.__overtime_hours - self.__deductions - self.__taxes, 2)

    @property
    def created_at(self) -> datetime:
        """Methode created_at : realise une partie de la logique de la classe."""
        return self.__created_at
