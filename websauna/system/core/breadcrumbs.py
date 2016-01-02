from pyramid.request import Request
from websauna.compat import typing
from websauna.system.core.interfaces import IRoot
from websauna.system.core.traverse import Resource
from zope.interface import Interface


def get_human_readable_resource_name(resource:Resource) -> str:
    """Extract human-readable name of the resource for breadcrumps."""

    # TODO: Add adapter implementation here

    if hasattr(resource, "get_title"):
        return resource.get_title()

    if hasattr(resource, "title"):
        return resource.title

    return resource.__name__


def get_breadcrumb(context:Resource, request:Request, root_iface:IRoot, current_view_name=None, current_view_url=None) -> typing.List:
    """Create breadcrumbs path data how to get to this resource from the root.

    Traverse context up to the root element in the reverse order.

    :param current_view_name: Optional user visible name of the current view for the bottom most resource.

    :param current_view_url: Full URL to the current view

    :param root_iface: If you want to traverse only subset of elements and stop a certain parent, optional root can be marked with an interface.

    :return: List of {url, name, resource} dictionaries
    """

    elems = []

    assert issubclass(root_iface, Interface), "Traversing root must be declared by an interface, got {}".format(root_iface)

    # Looks like it is not possible to dig out the matched view from Pyramid request,
    # so we need to explicitly pass it if we want it to appear in URL
    if current_view_name:
        assert current_view_url
        elems.append(dict(url=current_view_url, name=current_view_name))

    while context and not root_iface.providedBy(context):

        if not hasattr(context, "get_title"):
            raise RuntimeError("Breadcrumbs part missing get_title(): {}".format(context))

        elems.append(dict(url=request.resource_url(context), name=get_human_readable_resource_name(context), resource=context))

        if not hasattr(context, "__parent__"):
            raise RuntimeError("Broken traverse lineage on {}, __parent__ missing".format(context))

        if not isinstance(context, Resource):
            raise RuntimeError("Lineage has item not compatible with breadcrums: {}".format(context))

        context = context.__parent__

    # Add the last (root) element
    entry = dict(url=request.resource_url(context), name=get_human_readable_resource_name(context), resource=context)
    elems.append(entry)
    elems.reverse()

    return elems