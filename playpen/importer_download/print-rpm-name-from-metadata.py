import rpm, os, sys

def main(fname):
    fd = os.open(fname, os.O_RDONLY)
    ts = rpm.TransactionSet()
    # disable signature and digest checking for grabbing metadata
    ts.setVSFlags(-1)
    headers = ts.hdrFromFdno(fd)
    os.close(fd)

    if headers[rpm.RPMTAG_SOURCEPACKAGE]:
            print "%s-%s-%s.src.rpm" % (headers['name'], headers['version'], headers['release'])
    else:
            print "%s-%s-%s.%s.rpm" % (headers['name'], headers['version'], headers['release'], headers['arch'])

if __name__ == "__main__":
    main(sys.argv[1])
