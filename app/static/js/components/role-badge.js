/**
 * role-badge.js — Reusable role badge component.
 *
 * Props:
 *   name   String  Role name
 *   color  String  Color key: brand | blue | green | red | orange | purple | gray
 *   icon   String  FontAwesome class: fa-shield-halved | fa-user | ...
 *   href   String  Optional — renders as <a> with link (e.g. /admin/roles/3)
 *
 * Usage:
 *   <role-badge :name="item.role_name" :color="item.role_color"
 *               :icon="item.role_icon" :href="roleHref(item)">
 *   </role-badge>
 */
export default {
    name: 'RoleBadge',
    delimiters: ['[[', ']]'],
    props: {
        name:  { type: String, default: 'No role' },
        color: { type: String, default: 'gray' },
        icon:  { type: String, default: 'fa-user' },
        href:  { type: String, default: null },
    },
    template: `
    <component
        :is="href ? 'a' : 'span'"
        :href="href || undefined"
        :class="['rb', 'rb--' + (color || 'gray')]">
        <i :class="'fas ' + (icon || 'fa-user')"></i>
        [[ name || 'No role' ]]
    </component>
    `,
}
