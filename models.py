from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class BAA:
    """Simplified Binding Authority Agreement data structure.

    A BAA defines the parameters under which the coverholder may issue
    policies on behalf of a managing agent.  For this proof‑of‑concept
    we track only a handful of fields; real BAAs will include many
    more terms and clauses.
    """

    name: str
    start_date: datetime
    end_date: datetime
    territory: List[str]
    class_of_business: List[str]
    authority_limit: float
    required_endorsements: List[str] = field(default_factory=list)


@dataclass
class Policy:
    """Simplified representation of an individual policy.

    Policies are bound under a BAA and must comply with its terms.
    For this demo we store typical underwriting details along with
    textual content.  The textual content is the full policy wording
    or schedule; it is used by the AI extraction functions to derive
    the structured fields if they are not explicitly provided.
    """

    policy_number: str
    bind_date: datetime
    territory: str
    class_of_business: str
    sum_insured: float
    endorsements: List[str]
    text: Optional[str] = None  # full policy wording for AI extraction