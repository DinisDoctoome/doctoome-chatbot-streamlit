"""Centralized frontend-owned EN/FR interface strings."""

FEEDBACK_REASON_KEYS = (
    "misunderstood_request",
    "wrong_result",
    "missing_feature_or_filter",
    "too_many_questions",
    "technical_problem",
    "other",
)

TRANSLATIONS = {
    "en": {
        "interface_language": "Interface language",
        "english": "English",
        "french": "Français",
        "suggestion_title": "Have a suggestion?",
        "suggestion_help": "Tell us what you'd like us to improve or add.",
        "suggestion_placeholder": "Your suggestion",
        "suggestion_success": "Thank you for your suggestion.",
        "suggestion_error": "We couldn't save your suggestion. Please try again.",
        "feedback_question": "What went wrong?",
        "feedback_more": "Tell us more (optional)",
        "feedback_success": "Thank you for your feedback.",
        "feedback_error": "We couldn't save your feedback. Please try again.",
        "rating_error": "We couldn't save your rating. Please try again.",
        "submit": "Submit",
        "new_conversation": "New conversation",
        "message_placeholder": "Message the chatbot",
        "testing_interface": "Testing interface",
        "feedback_reason_misunderstood_request": "It misunderstood my request",
        "feedback_reason_wrong_result": "Wrong result",
        "feedback_reason_missing_feature_or_filter": "Missing feature or filter",
        "feedback_reason_too_many_questions": "Too many questions",
        "feedback_reason_technical_problem": "Technical problem",
        "feedback_reason_other": "Other",
    },
    "fr": {
        "interface_language": "Langue de l'interface",
        "english": "English",
        "french": "Français",
        "suggestion_title": "Une suggestion ?",
        "suggestion_help": "Dites-nous ce que vous aimeriez améliorer ou ajouter.",
        "suggestion_placeholder": "Votre suggestion",
        "suggestion_success": "Merci pour votre suggestion.",
        "suggestion_error": "Nous n'avons pas pu enregistrer votre suggestion. Réessayez.",
        "feedback_question": "Qu'est-ce qui n'a pas fonctionné ?",
        "feedback_more": "Dites-nous en plus (facultatif)",
        "feedback_success": "Merci pour votre retour.",
        "feedback_error": "Nous n'avons pas pu enregistrer votre retour. Réessayez.",
        "rating_error": "Nous n'avons pas pu enregistrer votre avis. Réessayez.",
        "submit": "Envoyer",
        "new_conversation": "Nouvelle conversation",
        "message_placeholder": "Écrivez au chatbot",
        "testing_interface": "Interface de test",
        "feedback_reason_misunderstood_request": "Il a mal compris ma demande",
        "feedback_reason_wrong_result": "Résultat incorrect",
        "feedback_reason_missing_feature_or_filter": "Fonctionnalité ou filtre manquant",
        "feedback_reason_too_many_questions": "Trop de questions",
        "feedback_reason_technical_problem": "Problème technique",
        "feedback_reason_other": "Autre",
    },
}


def translate(language: str, key: str) -> str:
    return TRANSLATIONS.get(language, TRANSLATIONS["en"])[key]


def feedback_reason_options(language: str) -> dict[str, str]:
    return {
        reason: translate(language, f"feedback_reason_{reason}") for reason in FEEDBACK_REASON_KEYS
    }


TRANSLATIONS["en"].update(
    {
        "internal_login": "Internal pilot — sign in with your assigned account",
        "email": "Email",
        "password": "Password",
        "sign_in": "Sign in",
        "sign_out": "Sign out",
        "invalid_login": "Email or password is incorrect.",
        "login_limited": "Too many login attempts. Try again in 15 minutes.",
        "access_unavailable": "Account and usage service unavailable. Please retry.",
        "conversations_left": "Conversations left today",
        "usage_unavailable": "Usage unavailable",
        "quota_reset": "New conversations available at",
        "retry": "Retry",
        "retry_message": "Retry last message",
        "quota_reached": "Daily limit reached. You can continue your current conversation.",
        "conversation_expired": "This conversation expired. Start a new conversation to continue.",
        "logout_failed": "Sign-out could not be confirmed. Please retry.",
    }
)
TRANSLATIONS["fr"].update(
    {
        "internal_login": "Pilote interne — connectez-vous avec votre compte attribué",
        "email": "E-mail",
        "password": "Mot de passe",
        "sign_in": "Se connecter",
        "sign_out": "Se déconnecter",
        "invalid_login": "E-mail ou mot de passe incorrect.",
        "login_limited": "Trop de tentatives. Réessayez dans 15 minutes.",
        "access_unavailable": "Service de compte et de quota indisponible. Réessayez.",
        "conversations_left": "Conversations restantes aujourd’hui",
        "usage_unavailable": "Quota indisponible",
        "quota_reset": "Nouvelles conversations disponibles à",
        "retry": "Réessayer",
        "retry_message": "Réessayer le dernier message",
        "quota_reached": "Limite quotidienne atteinte. Vous pouvez poursuivre la conversation en cours.",
        "conversation_expired": "Cette conversation a expiré. Démarrez une nouvelle conversation.",
        "logout_failed": "La déconnexion n’a pas pu être confirmée. Réessayez.",
    }
)

TRANSLATIONS["en"]["continue_after_failure"] = (
    "Continue conversation without replaying the failed message"
)
TRANSLATIONS["fr"]["continue_after_failure"] = "Poursuivre sans rejouer le message en échec"
