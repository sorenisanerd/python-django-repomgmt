class MyAuthBackend(object):
    def has_perm(self, user_obj, perm, obj=None):
        app, perm = perm.split('.')

        if app != 'repomgmt':
            return

        action, model_name = perm.split('_')

        if user_obj is not None:
            return getattr(obj, 'can_modify', lambda _: False)(user_obj)
