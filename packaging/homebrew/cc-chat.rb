# Homebrew formula TEMPLATE for the cc-chat engine.
#
# This is a starting point, not a finished formula. To produce a real one:
#
#   1. Publish the package to PyPI (or push a release tarball to GitHub).
#   2. Generate a formula skeleton from that URL:
#        brew create --python https://files.pythonhosted.org/.../<NAME>-0.1.0.tar.gz
#   3. Fill in the Python dependency `resource` blocks automatically:
#        brew update-python-resources Formula/cc-chat.rb
#   4. Host it in a personal tap repo `homebrew-<tap>` so users can:
#        brew tap <owner>/<tap>
#        brew install cc-chat
#
# The key win: `depends_on "toxcore"` means `brew install` pulls libtoxcore in
# automatically — the one native dependency the engine needs at runtime.

class CcChat < Formula
  include Language::Python::Virtualenv

  desc "Decentralized, encrypted, asynchronous CLI chat over the Tox protocol"
  homepage "https://github.com/JefferyLee/cc-chat"
  url "https://files.pythonhosted.org/packages/source/.../NAME-0.1.0.tar.gz" # TODO
  sha256 "TODO_FILL_IN_AFTER_RELEASE"
  license "TODO" # choose and add a LICENSE file

  depends_on "python@3.12"
  depends_on "toxcore" # pulls in libtoxcore (libsodium, libvpx, opus) automatically

  # TODO: `brew update-python-resources` generates the resource blocks for
  # `click` and any transitive deps here.
  # resource "click" do
  #   url "https://files.pythonhosted.org/.../click-8.1.7.tar.gz"
  #   sha256 "..."
  # end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Usage", shell_output("#{bin}/chat --help")
  end
end
