from typing import Dict, Any, Optional

def generate_clarification_email(
    service_name: str,
    organisation: str,
    original_purpose: str,
    evidence_type: str,
    evidence_source: Optional[str],
    evidence_date: Optional[str],
    evidence_quotes: list,
    data_categories: list,
    template: str = "general"
) -> Dict[str, str]:
    """
    Generate an editable plain-text clarification request email.
    Supports templates: "general", "dpdp", "gdpr", "ccpa".
    Tone: neutral, polite, non-accusatory.
    """
    source_info = f" ({evidence_source})" if evidence_source else ""
    date_info = f" received on {evidence_date}" if evidence_date else ""
    
    if evidence_quotes:
        quote_section = "In particular, the following statement was noted:\n" + "\n".join(
            [f'  > "{q}"' for q in evidence_quotes]
        )
    else:
        quote_section = "In particular, newly received disclosures mention secondary processing of user information."

    categories_str = ", ".join(data_categories) if data_categories else "my account information"

    if template == "dpdp":
        subject = f"Inquiry regarding Personal Data Processing under DPDP Act 2023 - {service_name}"
        body = f"""Dear Data Protection Officer / Grievance Officer, {organisation},

I am writing to you as a Data Principal regarding the personal data processed in connection with my account on {service_name}.

When I originally provided consent, the specified lawful purpose under Section 6 of the Digital Personal Data Protection Act (DPDP Act), 2023 was:
"{original_purpose.strip()}"

Recently, a {evidence_type}{source_info}{date_info} was issued that indicates additional data use:
{quote_section}

In accordance with Data Principal rights and Data Fiduciary obligations under the DPDP Act 2023, please provide clarification on the following points:

1. What is the specific, specified purpose for which this additional processing is carried out?
2. Which specific categories of personal data (such as {categories_str}) are involved?
3. Has this data been transferred to or shared with any third-party Data Processors or external entities? If so, what are their categories?
4. What is the lawful basis for this processing, and does it exceed the scope of my original consent?
5. How may I exercise my right to withdraw consent or register a grievance with your Grievance Redressal Mechanism under Section 13?

I request a written response within the statutory timeframes established by the DPDP Rules.

Thank you for your attention to this matter.

Sincerely,
[Your Name]
[Your Registered Email / Phone Number]
"""

    elif template == "gdpr":
        subject = f"Data Subject Inquiry: Purpose Limitation & Access Request (GDPR Art. 13/14 & 15) - {service_name}"
        body = f"""Dear Data Protection Officer, {organisation},

I am contacting you in my capacity as a data subject regarding the processing of my personal data under {service_name}.

Pursuant to Article 5(1)(b) of the General Data Protection Regulation (GDPR), personal data must be collected for specified, explicit, and legitimate purposes and not further processed in a manner incompatible with those purposes.

The original purpose for which my consent was collected was:
"{original_purpose.strip()}"

However, a subsequent {evidence_type}{source_info}{date_info} appears to introduce further processing:
{quote_section}

To ensure full transparency under Articles 13, 14, and 15 of the GDPR, please clarify:

1. What is the precise purpose and legal basis (Article 6 GDPR) for this additional processing activity?
2. Are personal data categories, specifically {categories_str}, included in this scope?
3. What recipients or categories of recipients (including third parties or commercial partners) have received or will receive my personal data?
4. If this is considered compatible further processing, what criteria under Article 6(4) were evaluated?
5. What mechanism is available for me to object (Article 21) or withdraw consent (Article 7(3)) without detriment to core services?

I look forward to receiving your response without undue delay and at the latest within one month of receipt.

Yours sincerely,
[Your Name]
[Your Account Email]
"""

    elif template == "ccpa":
        subject = f"Consumer Privacy Inquiry regarding Notice at Collection & Secondary Use (CCPA/CPRA) - {service_name}"
        body = f"""Dear Privacy Team, {organisation},

I am writing as a California consumer regarding the personal information collected in connection with {service_name}.

Under the California Consumer Privacy Act (CCPA), as amended by the CPRA (Cal. Civ. Code § 1798.100), a business must disclose at or before the point of collection the categories of personal information to be collected and the purposes for which it will be used, and shall not collect additional categories or use personal information for incompatible purposes without providing notice.

My original notice and consent specified the following primary purpose:
"{original_purpose.strip()}"

A recent {evidence_type}{source_info}{date_info} mentions further data handling:
{quote_section}

Please provide information on the following:

1. What are the specific business or commercial purposes for which this additional use is conducted?
2. Which categories of personal information (such as {categories_str}) are subject to this practice?
3. Does this practice constitute a "sale" or "sharing" of personal information under the CCPA/CPRA?
4. What third-party categories receive this data?
5. How can I exercise my right to opt out or limit the use of sensitive personal information?

Thank you for your prompt clarification.

Sincerely,
[Your Name]
[Your Account Email / Address]
"""

    else:  # General template
        subject = f"Request for clarification about use of my personal data - {service_name}"
        body = f"""Dear Privacy Team at {organisation},

I am writing to request clarification regarding the processing of my personal data in connection with {service_name}.

When I originally registered and provided consent, the stated purpose of processing was:
"{original_purpose.strip()}"

Recently, I received a {evidence_type}{source_info}{date_info} indicating additional data practices.
{quote_section}

Given that this appears to involve personal data categories such as {categories_str}, I would appreciate clarification on the following points:

1. For what specific purpose is the additional use mentioned?
2. Which of my personal data categories are involved?
3. Is my information shared with third parties? If so, which categories of recipients?
4. On what basis is this additional use carried out?
5. What choices do I have to opt out or withdraw consent?

I would appreciate your written response to these queries at your earliest convenience so that I can better understand how my personal data is being used.

Thank you for your time and assistance.

Sincerely,
[Your Name]
[Your Account Email / Username]
"""

    return {
        "subject": subject,
        "body": body
    }
