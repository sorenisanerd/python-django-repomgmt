class repomgmt:simple($user = 'ubuntu',admin_name = "Admin User",admin_email = "email@example.com",$dbname = "repomgmt",$dbuser = "repomgmt",$dbpass = "repomgmtpass",$dbhost = "",$dbport = "",$secret_key = '!tuy9ozxr@zhr$8v3$41^3690dfnrim16yj8x5)4pi0bg%140l',$ftp_ip = $::ipaddress,$post_mk_sbuild_customisation = undef) {
  $simple = true

  package { ["python-pip",
             "devscripts",
             "sbuild",
             "git",
             "apache2",
             "rabbitmq-server",
             "ubuntu-dev-tools",
             "reprepro",
             "haveged",
             "vsftpd"]:
    provider => "apt",
    ensure => "installed",
  }

  package { ["Django",
             "django-celery",
             "django-tastypie",
             "django-registration",
             "python-novaclient",
             "south"]:
    provider => "pip",
    ensure => "installed",
    require => Package['python-pip']
  }

  exec { "/usr/bin/pip install -e git+http://github.com/sorenh/python-django-repomgmt#egg=django-repomgmt":
    require => [Package['git'], Package['python-pip']]
  }

  user { "$user":
    ensure => "present",
    managehome => true,
    groups => "sbuild",
    require => Package['sbuild']
  }

  exec { "/usr/bin/django-admin startproject buildd":
    creates => "/home/$user/buildd",
    cwd => "/home/$user",
    user => $user
  } ->
  file { "/home/$user/buildd/buildd/settings.py":
    content => template('repomgmt/settings.py.erb'),
    owner => $user
  } ->
  file { "/home/$user/buildd/buildd/urls.py":
    content => template('repomgmt/urls.py.erb'),
    owner => $user
  } ~>
  exec { "/usr/bin/python /home/$user/buildd/manage.py syncdb --noinput":
    user => $user,
    refreshonly => true
  }

  file { "/etc/vsftpd.conf":
    content => template('repomgmt/vsftpd.conf.erb'),
    mode => 0644,
    owner => root,
    group => root,
    require => Package[vsftpd],
    notify => Exec["reload-vsftpd"]
  } 

  file { "/srv/ftp/incoming":
    ensure => directory,
    owner => $user,
    group => ftp,
    mode => "2711",
    require => Package[vsftpd],
  }

  exec { "reload-vsftpd":
    command => "/sbin/restart vsftpd",
    refreshonly => true
  }

  file { "/etc/apache2/conf.d/repomgmt.conf":
    content => template('repomgmt/apache.conf.erb'),
    owner => $user,
    require => Package["apache2"]
  } ~>
  exec { "/etc/init.d/apache2 reload":
    refreshonly => true
  } 
}
