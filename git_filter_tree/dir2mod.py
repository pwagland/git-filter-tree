"""
History rewrite helper script: Convert subfolder to submodule.

Usage:
    git-filter-tree dir2mod TREEMAP FOLDER URL [NAME] [-- REFS]

Arguments:

    TREEMAP     Path to tree index. For every top-level tree there should be
                a file $TREEMAP/$TREE_SHA1 that contains the SHA1 of the
                target commit.
    FOLDER      Subfolder to replace.
    URL         URL of the submodule
    NAME        Name of the submodule (defaults to FOLDER)
    REFS        `git-rev-list` options
"""

from .tree_filter import TreeFilter, cached, write_blob, read_blob

import multiprocessing
import os


class Dir2Mod(TreeFilter):

    def __init__(self, treemap, folder, url, name=None):
        super().__init__()
        self.treemap = treemap
        self.folder = tuple(folder.split('/'))
        self.url = url
        self.name = name or folder
        self.has_folder = multiprocessing.Manager().dict()
        self.has_gitmod = multiprocessing.Manager().dict()

    def depends(self, obj):
        return (obj.sha1, obj.path)

    @cached
    def rewrite_tree(self, obj):
        if obj.path == self.folder:
            self.has_folder[self._hash(obj.parent)] = True
            commit = open(os.path.join(self.treemap, obj.sha1)).read().strip()
            return [('160000', 'commit', commit, obj.name)]
        # only recurse into `self.folder`:
        elif obj.path == self.folder[:len(obj.path)]:
            ret = super().rewrite_tree(obj)
            if self.has_folder.get(self._hash(obj)):
                self.has_folder[self._hash(obj.parent)] = True
            return ret
        else:
            return [obj[:]]

    @cached
    def rewrite_file(self, obj):
        if obj.name == '.gitmodules' and obj.parent.parent is None:
            self.has_gitmod[self._hash(obj.parent)] = True
            return [self.gitmodules_file(obj.sha1)]
        return super().rewrite_file(obj)

    def map_tree(self, obj, entries):
        new_entries = super().map_tree(obj, entries)
        if (obj.parent is None
                and     self.has_folder.get(self._hash(obj))
                and not self.has_gitmod.get(self._hash(obj))):
            new_entries.append(self.gitmodules_file(None))
        return new_entries

    @cached
    def gitmodules_file(self, sha1):
        text = sha1 and read_blob(sha1) or ""
        sha1 = write_blob(text + """
[submodule "{}"]
    path = {}
    url = {}
"""[1:].format(self.name, '/'.join(self.folder), self.url))
        return ('100644', 'blob', sha1, '.gitmodules')


main = Dir2Mod.main
if __name__ == '__main__':
    import sys; sys.exit(main())
