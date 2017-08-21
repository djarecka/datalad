# emacs: -*- mode: python; py-indent-offset: 4; tab-width: 4; indent-tabs-mode: nil -*-
# ex: set sts=4 ts=4 sw=4 noet:
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the datalad package for the
#   copyright and license terms.
#
# ## ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
"""test command datalad run

"""

__docformat__ = 'restructuredtext'

import logging
from os.path import join as opj
from datalad.utils import chpwd

from datalad.distribution.dataset import Dataset
from datalad.support.exceptions import NoDatasetArgumentFound
from datalad.support.exceptions import CommandError
from datalad.tests.utils import ok_
from datalad.api import run
from datalad.tests.utils import assert_raises
from datalad.tests.utils import with_tempfile
from datalad.tests.utils import ok_clean_git
from datalad.tests.utils import create_tree
from datalad.tests.utils import eq_
from datalad.tests.utils import assert_status
from datalad.tests.utils import assert_result_count
from datalad.tests.utils import assert_in
from datalad.tests.utils import assert_not_in
from datalad.tests.utils import swallow_logs
from datalad.tests.utils import skip_if_on_windows


@with_tempfile(mkdir=True)
def test_invalid_call(path):
    with chpwd(path):
        # no dataset, no luck
        assert_raises(NoDatasetArgumentFound, run, 'doesntmatter')
        # dirty dataset
        ds = Dataset(path).create()
        create_tree(ds.path, {'this': 'dirty'})
        assert_status('impossible', run('doesntmatter', on_failure='ignore'))


@skip_if_on_windows
@with_tempfile(mkdir=True)
@with_tempfile(mkdir=True)
def test_basics(path, nodspath):
    ds = Dataset(path).create()
    last_state = ds.repo.get_hexsha()
    # run inside the dataset
    with chpwd(path):
        # runs nothing, does nothing
        assert_result_count(ds.run(), 0)
        eq_(last_state, ds.repo.get_hexsha())
        # provoke command failure
        with assert_raises(CommandError) as cme:
            ds.run('7i3amhmuch9invalid')
            # let's not speculate that the exit code is always 127
            ok(cme.code > 0)
        eq_(last_state, ds.repo.get_hexsha())
        # now one that must work
        res = ds.run('touch empty', message='TEST')
        ok_clean_git(ds.path)
        assert_result_count(res, 2)
        # TODO 'state' is still untracked!!!
        assert_result_count(res, 1, action='add', path=opj(ds.path, 'empty'), type='file')
        assert_result_count(res, 1, action='save', path=ds.path)
        commit_msg = ds.repo.repo.head.commit.message
        ok_(commit_msg.startswith('[DATALAD RUNCMD] TEST'))
        # crude test that we have a record for the PWD
        assert_in('"pwd": "."', commit_msg)
        last_state = ds.repo.get_hexsha()
        # now run a command that will not alter the dataset
        res = ds.run('touch empty', message='NOOP_TEST')
        assert_status('notneeded', res)
        eq_(last_state, ds.repo.get_hexsha())

    # run outside the dataset, should still work but with limitations
    with chpwd(nodspath):
        with swallow_logs(new_level=logging.WARNING) as cml:
            res = ds.run(['touch', opj(ds.path, 'empty2')], message='TEST')
            assert_status('ok', res)
            # we have been warned
            cml.assert_logged(".*not inside.*", level="WARNING")
            commit_msg = ds.repo.repo.head.commit.message
            # crude test that PWD wasn't recorded
            assert_not_in('"pwd": ', commit_msg)
