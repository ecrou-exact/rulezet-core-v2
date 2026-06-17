from ..core.db_class.config import NAV_POSITION_CHOICES, TOAST_POSITION_CHOICES, TOAST_STYLE_CHOICES, TOAST_DURATION_MIN, TOAST_DURATION_MAX


class VerifConfig:

    @staticmethod
    def verif_update(data: dict) -> dict:
        result = {}

        if 'theme' in data:
            from flask_login import current_user
            from ..features.config.config_core import get_valid_theme_keys
            is_admin = current_user.is_authenticated and current_user.is_admin()
            if data['theme'] not in get_valid_theme_keys(admin=is_admin):
                return {'message': "Invalid theme."}
            result['theme'] = data['theme']

        if 'nav_position' in data:
            if data['nav_position'] not in NAV_POSITION_CHOICES:
                return {'message': f"Invalid nav_position. Valid: {NAV_POSITION_CHOICES}"}
            result['nav_position'] = data['nav_position']

        if 'sidebar_collapsed' in data:
            if not isinstance(data['sidebar_collapsed'], bool):
                return {'message': 'sidebar_collapsed must be a boolean'}
            result['sidebar_collapsed'] = data['sidebar_collapsed']

        if 'toast_position' in data:
            if data['toast_position'] not in TOAST_POSITION_CHOICES:
                return {'message': f"Invalid toast_position. Valid: {TOAST_POSITION_CHOICES}"}
            result['toast_position'] = data['toast_position']

        if 'toast_style' in data:
            if data['toast_style'] not in TOAST_STYLE_CHOICES:
                return {'message': f"Invalid toast_style. Valid: {TOAST_STYLE_CHOICES}"}
            result['toast_style'] = data['toast_style']

        if 'toast_duration' in data:
            try:
                val = int(data['toast_duration'])
            except (TypeError, ValueError):
                return {'message': 'toast_duration must be an integer'}
            if not (TOAST_DURATION_MIN <= val <= TOAST_DURATION_MAX):
                return {'message': f"toast_duration must be between {TOAST_DURATION_MIN} and {TOAST_DURATION_MAX}"}
            result['toast_duration'] = val

        if not result:
            return {'message': 'No valid field provided'}

        return result
