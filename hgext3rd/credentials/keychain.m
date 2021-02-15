/*
 * keychain.m — native helpers for the macOS keychain
 */

#include <Foundation/Foundation.h>
#include <Security/Security.h>

#include <Python.h>

static const char *license =
    "Copyright © 2021, Dan Villiom Podlaski Christiansen"
    "\n\n"
    "Permission to use, copy, modify, and/or distribute this software"
    "for any purpose with or without fee is hereby granted, provided"
    "that the above copyright notice and this permission notice appear"
    "in all copies."
    "\n\n"
    "THE SOFTWARE IS PROVIDED \"AS IS\" AND THE AUTHOR DISCLAIMS ALL"
    "WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED"
    "WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE"
    "AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR"
    "CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS"
    "OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,"
    "NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN"
    "CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.";

static PyObject *KeychainError;

static NSString *unicode_to_string(PyObject *obj)
{
	NSStringEncoding encoding;
	void *data;
	if (obj == Py_None) {
		return nil;
	}
	if (PyBytes_Check(obj)) {
		data = PyBytes_AsString(obj);
		encoding = NSUTF8StringEncoding;
	} else {
		obj = PyObject_Str(obj);

		if (obj == NULL) {
			return nil;
		}

#ifdef Py_LIMITED_API
		// convert to utf8 bytes object
		obj = PyUnicode_AsUTF8String(obj);
		data = PyBytes_AsString(obj);
		encoding = NSUTF8StringEncoding;
#else

		switch (PyUnicode_KIND(obj)) {
		case PyUnicode_WCHAR_KIND:
			encoding = sizeof(wchar_t) == 2 ? NSUTF16StringEncoding
			                                : NSUTF32StringEncoding;
			break;

		case PyUnicode_1BYTE_KIND:
			encoding = NSISOLatin1StringEncoding;
			break;

		case PyUnicode_2BYTE_KIND:
			encoding = NSUTF16StringEncoding;
			break;

		case PyUnicode_4BYTE_KIND:
			encoding = NSUTF32StringEncoding;
			break;
		default:
			abort();
		}

		data = PyUnicode_DATA(obj);
#endif
	}

	return [NSString stringWithCString:data encoding:encoding];
}

static PyObject *string_to_unicode(NSString *str)
{
	const char *data = [str UTF8String];

	return PyUnicode_DecodeUTF8(data, strlen(data), NULL);
}

static PyObject *data_to_unicode(NSData *data)
{
	return PyUnicode_DecodeUTF8([data bytes], [data length], NULL);
}

static BOOL is_debug_enabled(PyObject *ui)
{
	if (!PyObject_HasAttrString(ui, "debugflag")) {
		return NO;
	}

	PyObject *debugflag = PyObject_GetAttrString(ui, "debugflag");

	return PyObject_IsTrue(debugflag);
}

static void debug(PyObject *ui, NSString *str)
{
	if (is_debug_enabled(ui)) {
		PyObject_CallMethod(ui, "debug", "y", [str UTF8String]);
	}
}

static void note(PyObject *ui, NSString *str)
{
	PyObject_CallMethod(ui, "note", "y", [str UTF8String]);
}

static NSString *getattrstring(PyObject *obj, const char *attrname)
{
	PyObject *attrval = PyObject_GetAttrString(obj, attrname);

	if (attrval == NULL) {
		return nil;
	}

	return unicode_to_string(attrval);
}

static NSNumber *getattrlong(PyObject *obj, const char *attrname)
{
	PyObject *attrval = PyObject_GetAttrString(obj, attrname);

	if (attrval == NULL) {
		return nil;
	}

	attrval = PyNumber_Long(attrval);

	if (attrval == NULL) {
		return nil;
	}

	return @(PyNumber_AsSsize_t(attrval, NULL));
}

static NSData *getattrdata(PyObject *obj, const char *attrname)
{
	PyObject *attrval = PyObject_GetAttrString(obj, attrname);

	if (attrval == NULL) {
		return nil;
	}

	if (PyUnicode_Check(attrval)) {
		attrval = PyUnicode_AsUTF8String(attrval);
	}

	const char *buffer = PyBytes_AsString(attrval);

	if (attrval == NULL) {
		return nil;
	}

	return [NSData dataWithBytes:buffer length:PyBytes_Size(attrval)];
}

static NSString *getprotocol(PyObject *url)
{
	NSString *scheme = getattrstring(url, "scheme");
	OSType protocol;

	if ([@"https" isEqualToString:scheme]) {
		protocol = kSecProtocolTypeHTTPS;
	} else if ([@"http" isEqualToString:scheme]) {
		protocol = kSecProtocolTypeHTTP;
	} else if ([@"smtp" isEqualToString:scheme]) {
		protocol = kSecProtocolTypeSMTP;
	} else {
		// unsupported!
		return nil;
	}

	return NSFileTypeForHFSTypeCode(protocol);
}

static NSDictionary *get_attrs(PyObject *ui, PyObject *url)
{
	NSNumber *port = getattrlong(url, "port");
	NSString *user = getattrstring(url, "user");
	NSString *host = getattrstring(url, "host");
	NSString *label =
	    [NSString stringWithFormat:@"Mercurial (%@@%@)", user, host];

	NSMutableDictionary *r = [NSMutableDictionary new];

	r[(id)kSecClass] = (id)kSecClassInternetPassword;
	r[(id)kSecAttrLabel] = label;
	r[(id)kSecAttrAccount] = user;
	r[(id)kSecValueData] = getattrdata(url, "passwd");
	r[(id)kSecAttrServer] = host;
	r[(id)kSecAttrPath] = getattrstring(url, "path");
	r[(id)kSecAttrSecurityDomain] = getattrstring(url, "realm");
	r[(id)kSecAttrProtocol] = getprotocol(url);

	if (port != nil) {
		r[(id)kSecAttrPort] = port;
	}

	return [NSDictionary dictionaryWithDictionary:r];
}

static NSDictionary *get_query(PyObject *ui, PyObject *url)
{
	NSMutableDictionary *r = [NSMutableDictionary new];

	r[(id)kSecClass] = (id)kSecClassInternetPassword;
	r[(id)kSecAttrServer] = getattrstring(url, "host");
	r[(id)kSecAttrPath] = getattrstring(url, "path");
	r[(id)kSecAttrSecurityDomain] = getattrstring(url, "realm");
	r[(id)kSecAttrProtocol] = getprotocol(url);
	r[(id)kSecMatchLimit] = (id)kSecMatchLimitOne;
	r[(id)kSecReturnAttributes] = @YES;
	r[(id)kSecReturnData] = @YES;

	if (PyObject_HasAttrString(url, "user")) {
		NSString *s = getattrstring(url, "user");
		if (s != nil) {
			r[(id)kSecAttrAccount] = getattrstring(url, "user");
		}
	}

	if (PyObject_HasAttrString(url, "port")) {
		NSNumber *port = getattrlong(url, "port");
		if (port != nil) {
			r[(id)kSecAttrPort] = port;
		}
	}

	if (PyObject_HasAttrString(url, "realm")) {
		NSString *s = getattrstring(url, "realm");
		if (s != nil) {
			r[(id)kSecAttrSecurityDomain] = s;
		}
	}

	if (is_debug_enabled(ui)) {
		NSString *debugstr =
		    [NSString stringWithFormat:@"querying keychain: %@\n", r];

		debug(ui, debugstr);
	}

	return [NSDictionary dictionaryWithDictionary:r];
}

static PyObject *save_password(PyObject *self, PyObject *args)
{
	PyObject *ui, *url;

	if (!PyArg_UnpackTuple(args, "save_password", 2, 2, &ui, &url))
		return NULL;

	if (getprotocol(url) == nil) {
		PyErr_SetString(PyExc_ValueError, "unsupported protocol");
		return NULL;
	}

	NSDictionary *query = get_query(ui, url);
	NSDictionary *attrs = get_attrs(ui, url);
	OSStatus err;

	Py_BEGIN_ALLOW_THREADS;

	err = SecItemUpdate((__bridge CFDictionaryRef)query,
	                    (__bridge CFDictionaryRef)attrs);

	Py_END_ALLOW_THREADS;

	if (err == errSecItemNotFound) {
		debug(ui, @"adding new keychain item\n");

		Py_BEGIN_ALLOW_THREADS;

		err = SecItemAdd((__bridge CFDictionaryRef)attrs, NULL);

		Py_END_ALLOW_THREADS;
	}

	if (err != errSecSuccess) {
		NSString *errstr =
		    CFBridgingRelease(SecCopyErrorMessageString(err, NULL));
		PyErr_SetString(KeychainError, [errstr UTF8String]);
		return NULL;
	}

	Py_RETURN_NONE;
}

static PyObject *find_password(PyObject *self, PyObject *args)
{
	PyObject *ui, *url;

	if (!PyArg_UnpackTuple(args, "find_password", 2, 2, &ui, &url))
		return NULL;

	if (getprotocol(url) == nil) {
		PyErr_SetString(PyExc_ValueError, "unsupported protocol");
		return NULL;
	}

	NSDictionary *query = get_query(ui, url);
	CFTypeRef cfresult;
	OSStatus err;

	Py_BEGIN_ALLOW_THREADS;

	err = SecItemCopyMatching((CFDictionaryRef)query, &cfresult);

	Py_END_ALLOW_THREADS;

	if (err == errSecItemNotFound) {
		return PyTuple_Pack(2, Py_None, Py_None);
	} else if (err != noErr) {
		NSString *errstr = (NSString *)CFBridgingRelease(
		    SecCopyErrorMessageString(err, NULL));
		PyErr_SetString(KeychainError, [errstr UTF8String]);
		return NULL;
	}

	NSDictionary *result = CFBridgingRelease(cfresult);

	NSString *user = result[(id)kSecAttrAccount];
	NSData *passwd = result[(id)kSecValueData];

	PyObject *userobj, *passwdobj;

	if (user != NULL) {
		userobj = string_to_unicode(user);
	} else {
		userobj = Py_None;
	}

	if (passwd != NULL) {
		passwdobj = data_to_unicode(passwd);
	} else {
		passwdobj = Py_None;
	}

	NSDate *date = result[(id)kSecAttrModificationDate];
	NSString *label = result[(id)kSecAttrLabel];

	NSString *debugstr = [NSString
	    stringWithFormat:@"using keychain item '%@' modified on %@\n",
	                     label, date];

	note(ui, debugstr);

	return PyTuple_Pack(2, userobj, passwdobj);
}

static PyMethodDef KeychainMethods[] = {
    {
        "save_password",
        save_password,
        METH_VARARGS,
        "Save a password in the Keychain.",
    },
    {
        "find_password",
        find_password,
        METH_VARARGS,
        "Find a password in the Keychain.",
    },
    {NULL, NULL, 0, NULL} /* Sentinel */
};

static struct PyModuleDef keychainmodule = {
    PyModuleDef_HEAD_INIT,
    /* name of module */
    "hgext3rd.keychain",
    /* module documentation, may be NULL */
    "hgext3rd.keychain - native helpers for the macOS keychain",
    /* size of per-interpreter state of the module,
       or -1 if the module keeps state in global variables. */
    -1,
    KeychainMethods,
};

PyMODINIT_FUNC PyInit_keychain(void)
{
	PyObject *m;

	m = PyModule_Create(&keychainmodule);
	if (m == NULL)
		return NULL;

	KeychainError = PyErr_NewExceptionWithDoc(
	    "keychain.KeychainError", "Keychain-related errors", NULL, NULL);

	Py_XINCREF(KeychainError);

	if (PyModule_AddObject(m, "KeychainError", KeychainError) < 0) {
		Py_XDECREF(KeychainError);
		Py_CLEAR(KeychainError);
		Py_DECREF(m);
		return NULL;
	}

	PyObject *licenseobj = PyUnicode_FromString(license);

	if (PyModule_AddObject(m, "_license", licenseobj) < 0) {
		return NULL;
	}

	return m;
}
