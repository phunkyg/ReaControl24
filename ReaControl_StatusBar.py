#!/usr/bin/python

import sys, os


OPTIONS = [
    'Start',
    'Stop',
    'Status'
]

def main():
    for i in OPTIONS:
       print i

def handler(value):
    option = None
    for x in OPTIONS:
        if x == value:
            option = value
            break

    if option:
        if option == 'Start':
            os.system('echo hello > /Users/Shared/test.log >&2 &')
        elif option == 'Stop':
            pass
        elif option == 'Status':
            pass

def debug(value, option):
    with open('/Users/Shared/testfile.txt', 'w') as f:
        f.write(value)
        f.write(option)

if __name__ == '__main__':
    main()
    print("Arguments count: {}".format(len(sys.argv)))
    for i, arg in enumerate(sys.argv):
        print("Argument {}: {}".format(i,arg))
        handler(arg)

